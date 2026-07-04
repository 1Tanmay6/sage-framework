import sys
import time
import docker
import httpx
from ..utils import load_config
from ...globals import setup_logger
from typing import Literal


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

            # Verify the container exists right away during initialization
            self._verify_container_exists()

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

    def ensure_qdrant(self, timeout: float = 15):
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


if __name__ == '__main__':
    # Initialize the instance and automatically trigger health check/startup
    vector_db = VectorDB(runtime_env='local')
    vector_db.ensure_qdrant()
