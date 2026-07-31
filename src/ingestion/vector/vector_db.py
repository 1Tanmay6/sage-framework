import sys
import time
import docker
import httpx
from tqdm import tqdm
from ..core import load_config
from ...globals import setup_logger
from typing import Literal
from langchain_ollama import OllamaEmbeddings
from qdrant_client.models import Distance, VectorParams
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore


class VectorDB:
    def __init__(
            self,
            runtime_env: Literal['local', 'cloud'],
            config_path: str = './config/ingestion_config.yaml'
    ):
        self._config = load_config(config_path=config_path)
        self._logger = setup_logger(__name__)
        self._qdrant_url: str
        self._container_name: str
        self._client: any = None
        self._embeddings: any = OllamaEmbeddings(
            model=self._config['embedding_model'])

        if runtime_env == 'local':
            self._container_name = self._config['qdrant'][runtime_env]['docker_container_name']
            self._qdrant_host = self._config['qdrant'][runtime_env]['host']
            self._qdrant_port = int(
                self._config['qdrant'][runtime_env]['port'])
            self._qdrant_url = self._build_qdrant_url(
                host=self._qdrant_host,
                port=self._qdrant_port,
                runtime_env=runtime_env
            )
        else:
            raise NotImplementedError(
                "The current system supports only 1 runtime environment: local.")

    def _build_qdrant_url(
            self,
            host: str,
            port: int,
            runtime_env: Literal['local', 'cloud']
    ) -> str:
        """Builds a URL for accessing Qdrant."""
        if runtime_env == 'local':
            return f"http://{host}:{port}"
        elif runtime_env == 'cloud':
            raise NotImplementedError("Cloud environment not implemented yet.")
        else:
            raise KeyError(
                "The current system supports only 1 runtime environment: local.")

    def _verify_container_exists(self) -> None:
        """Validates that the configured container actually exists in Docker daemon."""
        try:
            client = docker.from_env()
            client.containers.get(self._container_name)
            self._logger.debug(
                f"Container '{self._container_name}' successfully verified.")
        except docker.errors.NotFound:
            self._logger.critical(
                f"Configured container '{self._container_name}' does not exist on this machine. "
                "Please create the container before running the script."
            )
            sys.exit(1)
        except docker.errors.APIError as e:
            self._logger.critical(
                f"Failed to communicate with Docker daemon: {e}")
            sys.exit(1)

    def _is_qdrant_running(self) -> bool:
        """Checks if the Qdrant container is running and responding to HTTP requests."""
        try:
            client = docker.from_env()
            # 1. Check if the container exists and is running in Docker
            container = client.containers.get(self._container_name)
            if container.status != "running":
                return False

            # 2. Check if the Qdrant service inside is actually ready to accept traffic
            # Appending /healthz to check Qdrant service readiness
            response = httpx.get(f"{self._qdrant_url}/healthz", timeout=2.0)
            return response.status_code == 200

        except (docker.errors.NotFound, docker.errors.APIError):
            # Container dropped or Docker daemon suddenly became unreachable
            return False
        except httpx.HTTPError:
            # Catches ReadError (Connection reset), ConnectError, TimeoutException, etc.
            # This safely flags that the service is still initializing
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error occurred: {e}")
            self.logger.warning(
                "Check if you have docker daemon up and running")
            return False

    def _ensure_qdrant(self, timeout: float = 15):
        """Starts the Qdrant container if it's not running. 

        Kills the script with exit code 1 if it fails to start.
        """
        if self._is_qdrant_running():
            self._logger.info("Qdrant is already up and running.")
            return

        self._logger.warning(
            "Qdrant is not running. Attempting to start the container...")
        try:
            client = docker.from_env()
            container = client.containers.get(self._container_name)
            container.start()

            # Poll the health check endpoint until it's ready or times out
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self._is_qdrant_running():
                    self._logger.info(
                        "Qdrant started and initialized successfully!")
                    return
                time.sleep(1)

            self._logger.critical(
                f"Qdrant container started, but failed health checks within {timeout} seconds."
            )
            sys.exit(1)

        except docker.errors.NotFound:
            self._logger.critical(
                f"Container '{self._container_name}' not found. Please create it first."
            )
            sys.exit(1)
        except docker.errors.APIError as e:
            self._logger.critical(
                f"Docker API error occurred while starting container: {e}")
            sys.exit(1)

    def _create_client(self) -> tuple:
        """Create a new Qdrant client."""
        self._verify_container_exists()
        self._ensure_qdrant()
        try:
            self._client = QdrantClient(url=self._qdrant_url)
            return self._client, True
        except Exception as e:
            self._logger.error(f"Failed to create Qdrant vector store: {e}")
            return None, False

    def get_client(self):
        """Get an active client for intercting with the vector"""
        if self._client is None:
            self._logger.info(f"No active client found attempting connection")
            client, flag = self._create_client()
            if flag:
                self._logger.info(f"Client Created. Connection Established")
                return client
            else:
                self._logger.error(
                    f"Failed to create client. Connection not established")
                return None
        else:
            self._logger.info("Active client found")
            return self._client

    def list_collection(self) -> list[str]:
        """List all collection names in the Qdrant instance.

        Returns a list of collection name strings, or an empty list
        if no connection can be established or an error occurs.
        """
        if self._client is None:
            self._logger.warning(
                "No active Qdrant client. Attempting to establish connection before listing collections.")
            client = self.get_client()
            if client is None:
                self._logger.error(
                    "Cannot list collections: no client connection.")
                return []

        try:
            response = self._client.get_collections()
            names = [c.name for c in response.collections]
            self._logger.info(
                f"Found {len(names)} collection(s): {names}")
            return names
        except Exception as e:
            self._logger.error(
                f"Failed to list collections: {e}")
            return []

    def create_collection(self, collection_name: str) -> bool:
        """Create a new collection in the vector store."""
        try:
            self._logger.info(
                f"Creating collection '{collection_name}' in Qdrant.")
            vector_size = len(self._embeddings.embed_query("test"))

            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            self._logger.info(
                f"Collection '{collection_name}' created successfully.")
            return True
        except Exception as e:
            self._logger.error(
                f"Failed to create collection '{collection_name}': {e}")
            return False

    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection from the vector store.

        Returns True if the collection was deleted (or did not exist),
        False if an error occurred during deletion.
        """
        if self._client is None:
            self._logger.warning(
                "No active Qdrant client. Attempting to establish connection before deletion.")
            client = self.get_client()
            if client is None:
                self._logger.error(
                    f"Cannot delete collection '{collection_name}': no client connection.")
                return False

        try:
            if not self._client.collection_exists(collection_name=collection_name):
                self._logger.warning(
                    f"Collection '{collection_name}' does not exist. Nothing to delete.")
                return True

            self._client.delete_collection(collection_name=collection_name)
            self._logger.info(
                f"Collection '{collection_name}' deleted successfully.")
            return True
        except Exception as e:
            self._logger.error(
                f"Failed to delete collection '{collection_name}': {e}")
            return False

    def add_documents(self, chunks: list, batch_size: int, vdb_client: any) -> bool:
        try:
            self._logger.info("Adding documents to Qdrant")
            if len(chunks) > batch_size:
                for i in tqdm(range(0, len(chunks), batch_size), desc="Embedding & Ingesting"):
                    batch = chunks[i: i + batch_size]
                    vdb_client.add_documents(batch)
            self._logger.info("Ingestion Completed for this batch")
            return True
        except Exception as e:
            self._logger.error(f"Error during ingestion: {e}")
            return False


if __name__ == '__main__':
    # Initialize the instance and automatically trigger health check/startup
    vector_db = VectorDB(runtime_env='local')
    vector_db.ensure_qdrant()
