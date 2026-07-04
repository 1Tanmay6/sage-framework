import math
import random
from langchain_qdrant import QdrantVectorStore
from pathlib import Path
from ...globals import setup_logger

# Initialize the module-level logger
logger = setup_logger(__name__)


def generate_gaussian_dict(
        mini: float = 500,
        maxi: float = 1000,
        jump: float = 25,
        mean: float = 750,
        std_dev: float = 168
) -> dict[str, float]:
    """
    Generates a dictionary with values from a Gaussian distribution.
    """
    logger.debug(
        f"Generating Gaussian chunk config (Bounds: {mini}-{maxi}, Mean: {mean}, StdDev: {std_dev})")

    # Ensure range bounds are valid integers for the range function
    values = list(range(int(mini), int(maxi), int(jump)))

    weights = [math.exp(-((x - mean) ** 2) / (2 * std_dev ** 2))
               for x in values]

    chosen_number = random.choices(values, weights=weights, k=1)[0]
    overlap = chosen_number * 0.20

    logger.debug(
        f"Gaussian distribution selected chunk_size: {chosen_number} | overlap_size: {overlap:.1f}")

    return {
        "chunk_size": chosen_number,
        "overlap_size": overlap
    }


def random_relevant_chunks_retrieval(
        client: str,
        filename: str,
        embeddings: any,
        collection_name: str,
        query: str,
        fetch_k: int = 20,
        lambda_mult: float = 0.75,
        mini_k: int = 5,
        maxi_k: int = 8
) -> tuple:
    """
    Retrieves a random set of relevant chunks based on a query.
    """
    k = random.randint(mini_k, maxi_k)
    logger.info(
        f"Initiating MMR search. Query: '{query}' | Selected Target K: {k} (Range: {mini_k}-{maxi_k})")

    other_context_metadata = []
    final_chunks_content = []

    try:
        qdrant_store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
        )

        results = qdrant_store.max_marginal_relevance_search(
            query=query,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult
        )
    except Exception as e:
        logger.error(
            f"Failed executing MMR search in collection '{collection_name}'. Error: {str(e)}", exc_info=True)
        return [], []

    skipped_count = 0
    for res in results:
        source_path = res.metadata.get("source", "")
        if not source_path:
            logger.warning(
                "Found a retrieved document chunk with missing source metadata.")
            continue

        # Parse the filename safely
        chunk_filename = Path(source_path).stem + ".jsonl"

        # Exclude chunks belonging to the file currently being evaluated
        if chunk_filename == filename:
            skipped_count += 1
            continue

        other_context_metadata.append(source_path)
        final_chunks_content.append(res.page_content)

    logger.info(
        f"MMR Extraction complete. Retrieved: {len(results)} chunks | "
        f"Accepted: {len(final_chunks_content)} | Filtered (Self-source matches): {skipped_count}"
    )

    return other_context_metadata, final_chunks_content


def insert_metadata_with_favored_middle(
        lst: list,
        item: any,
        weights: list[float] = [15, 70, 15]
) -> tuple[list, str, int]:
    """
    Inserts an item into a list favoring the middle [2 to n-2].
    Returns the new list, the placement label, and the exact index of insertion.
    """
    n = len(lst)
    new_lst = lst.copy()

    logger.debug(f"Inserting item into list. Current list length: {n}")

    if n < 4:
        idx = random.randint(0, n)
        logger.debug(
            f"List length too short ({n} < 4) for weighted profile strategy. Fallback random index chosen: {idx}")
    else:
        category = random.choices(
            population=['START', 'MIDDLE', 'END'],
            weights=weights,
            k=1
        )[0]

        if category == 'START':
            idx = random.choice([0, 1])
        elif category == 'END':
            idx = random.choice([n - 1, n])
        else:
            idx = random.randint(2, n - 2)

        logger.debug(
            f"Weighted category chosen: {category}. Calculated insertion index: {idx}")

    new_lst.insert(idx, item)

    # Post-placement label reconciliation
    if idx <= 1:
        label = 'START'
    elif idx >= n - 1:
        label = 'END'
    else:
        label = 'MIDDLE'

    logger.info(
        f"Successfully placed item at index {idx} with structural classification label: '{label}'")

    return new_lst, label, idx
