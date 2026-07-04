import os
import json
import yaml
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
from ...globals import setup_logger, log_time

logger = setup_logger(__name__)


def save_chunks_to_jsonl(
        chunks: list,
        output_folder: str
) -> None:
    """
    Groups text chunks by their source metadata and saves them into respective .jsonl files.
    """
    if not chunks:
        logger.warning(
            "save_chunks_to_jsonl received an empty chunks list. Skipping operation.")
        return

    logger.info(
        f"Starting JSONL saving process for {len(chunks)} chunks into folder: {output_folder}")
    os.makedirs(output_folder, exist_ok=True)

    grouped_chunks = {}

    for chunk in tqdm(chunks, desc="Grouping Chunks"):
        if hasattr(chunk, 'metadata') and hasattr(chunk, 'page_content'):
            source = chunk.metadata.get('source', 'unknown_source')
            chunk_data = {
                "page_content": chunk.page_content,
                "metadata": chunk.metadata
            }
        else:
            source = chunk.get('metadata', {}).get('source', 'unknown_source')
            chunk_data = chunk

        if source not in grouped_chunks:
            grouped_chunks[source] = []
        grouped_chunks[source].append(chunk_data)

    logger.debug(
        f"Grouped {len(chunks)} chunks into {len(grouped_chunks)} distinct source files.")

    # Tracking metrics for the final summary log
    files_saved_count = 0

    for source_path, items in tqdm(grouped_chunks.items(), desc="Saving Chunks to JSONL"):
        base_filename = Path(source_path).stem

        if not base_filename:
            base_filename = "unknown_source"

        output_filepath = os.path.join(output_folder, f"{base_filename}.jsonl")

        # FIX Applied: Changed 'w' to 'a' so multi-batch processing appends safely
        try:
            with open(output_filepath, 'a', encoding='utf-8') as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
            files_saved_count += 1
            logger.debug(
                f"Successfully appended {len(items)} chunks to {output_filepath}")
        except Exception as e:
            logger.error(
                f"Failed to write chunks to {output_filepath}. Error: {str(e)}", exc_info=True)

    logger.info(
        f"JSONL saving completed. Successfully updated/created {files_saved_count} .jsonl files.")


def sync_metadata(
        metadata_lock: any,
        metadata_path: str,
        selected: list[str],
        processed: list[str],
        unprocessed: list[str]
) -> None:
    logger.info(f"Attempting to sync tracking metadata to: {metadata_path}")

    with metadata_lock:
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "selected_files": selected,
            "processed_files": processed,
            "unprocessed_files": unprocessed
        }
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4)
            logger.info(
                f"Metadata sync successful. Summary -> Selected: {len(selected)} | "
                f"Processed: {len(processed)} | Unprocessed: {len(unprocessed)}"
            )
        except Exception as e:
            logger.critical(
                f"Critical failure writing metadata sync file to {metadata_path}! Error: {str(e)}")


def append_to_output(
        output_lock: any,
        output_path: str,
        records: list[any]
) -> None:
    if not records:
        logger.debug(
            "append_to_output called with an empty records list. No write required.")
        return

    logger.debug(
        f"Waiting for thread-lock to append {len(records)} records to main output: {output_path}")

    with output_lock:
        try:
            with open(output_path, 'a', encoding='utf-8') as f:
                for record in records:
                    f.write(json.dumps(record) + '\n')
            logger.debug(
                f"Successfully appended {len(records)} records to {output_path}")
        except Exception as e:
            logger.error(
                f"Failed appending records to output tracking file {output_path}. Error: {str(e)}")


@log_time
def load_config(config_path: str) -> dict[str, any]:
    """
        Loads a YAML file from a config file path and returns the configuration dictionary.
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            logger.info(
                f"configuration loaded successfully from {config_path}")
            return config
    except Exception as e:
        logger.error(
            "Failed to load configuration file. Error: {str(e)}"
        )


if __name__ == "__main__":
    # Example usage
    config = load_config('./config/ingestion_config.yaml')
    print(config)
