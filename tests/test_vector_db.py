"""
Tests for VectorDB collection-manipulation methods.

Covers:
    get_client()        -> establishes a Qdrant connection (auto-starts container)
    list_collection()   -> lists existing collections
    create_collection() -> creates a new collection
    delete_collection() -> deletes a collection (idempotently)

These tests run against a THROWAWAY collection so real data
(e.g. 'cleaned_silver_vdb') is never modified.

Prerequisites (tests are skipped, not failed, when unmet):
    1. Docker daemon running, with the Qdrant container from
       config/ingestion_config.yaml present (auto-started if stopped).
    2. Ollama serving the configured embedding model — required by
       create_collection to infer the vector size.

Run from the project root:
    pytest tests/test_vector_db.py -v
"""

import pytest

from src.ingestion.vector.vector_db import VectorDB

# Throwaway collection used exclusively by this test module.
TEST_COLLECTION = "sage_test_vector_db_pytest"


def _connect_or_skip() -> VectorDB:
    """Return a connected VectorDB, or skip the calling test if unavailable."""
    try:
        vdb = VectorDB(runtime_env="local")
    except SystemExit:
        pytest.skip("Qdrant/Docker unavailable (VectorDB aborted on startup).")
    except Exception as exc:  # noqa: BLE001 - surface any init failure as a skip
        pytest.skip(f"VectorDB init failed: {exc}")

    if vdb.get_client() is None:
        pytest.skip("Could not establish a Qdrant client connection.")
    return vdb


@pytest.fixture(scope="module")
def vdb() -> VectorDB:
    """A single connected VectorDB shared across the module (expensive to build)."""
    return _connect_or_skip()


@pytest.fixture(autouse=True)
def clean_test_collection(vdb: VectorDB):
    """Guarantee isolation: the throwaway collection is absent before AND after
    every test, regardless of pass/fail. Makes the suite repeatable."""
    vdb.delete_collection(TEST_COLLECTION)
    yield
    vdb.delete_collection(TEST_COLLECTION)


# --------------------------------------------------------------------------- #
# get_client                                                                  #
# --------------------------------------------------------------------------- #

def test_get_client_returns_connection(vdb: VectorDB):
    assert vdb.get_client() is not None


# --------------------------------------------------------------------------- #
# list_collection                                                             #
# --------------------------------------------------------------------------- #

def test_list_collection_returns_list(vdb: VectorDB):
    result = vdb.list_collection()
    assert isinstance(result, list)
    assert all(isinstance(name, str) for name in result)


# --------------------------------------------------------------------------- #
# create_collection                                                           #
# --------------------------------------------------------------------------- #

def test_create_collection_returns_true(vdb: VectorDB):
    assert vdb.create_collection(TEST_COLLECTION) is True


def test_created_collection_appears_in_list(vdb: VectorDB):
    vdb.create_collection(TEST_COLLECTION)
    assert TEST_COLLECTION in vdb.list_collection()


def test_create_duplicate_collection_returns_false(vdb: VectorDB):
    """Qdrant rejects duplicate names; the method should return False, not raise."""
    assert vdb.create_collection(TEST_COLLECTION) is True
    assert vdb.create_collection(TEST_COLLECTION) is False


# --------------------------------------------------------------------------- #
# delete_collection                                                           #
# --------------------------------------------------------------------------- #

def test_delete_collection_returns_true(vdb: VectorDB):
    vdb.create_collection(TEST_COLLECTION)
    assert vdb.delete_collection(TEST_COLLECTION) is True


def test_deleted_collection_absent_from_list(vdb: VectorDB):
    vdb.create_collection(TEST_COLLECTION)
    vdb.delete_collection(TEST_COLLECTION)
    assert TEST_COLLECTION not in vdb.list_collection()


def test_delete_nonexistent_collection_is_idempotent(vdb: VectorDB):
    """Deleting a collection that doesn't exist should still return True."""
    assert vdb.delete_collection(TEST_COLLECTION) is True


# --------------------------------------------------------------------------- #
# Full lifecycle                                                              #
# --------------------------------------------------------------------------- #

def test_full_collection_lifecycle(vdb: VectorDB):
    assert TEST_COLLECTION not in vdb.list_collection()

    assert vdb.create_collection(TEST_COLLECTION) is True
    assert TEST_COLLECTION in vdb.list_collection()

    assert vdb.delete_collection(TEST_COLLECTION) is True
    assert TEST_COLLECTION not in vdb.list_collection()
