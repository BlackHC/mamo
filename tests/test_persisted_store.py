from os import mkdir, listdir, path

import pytest

from mamo.internal.identities import value_name_identity
from mamo.internal.persisted_store import PersistedStore
from mamo.internal.weakref_utils import ObjectProxy

from tests.testing import BoxedValue

import tempfile


def test_persisted_store_memory_only_add_works():
    store = PersistedStore.from_memory()

    vid = value_name_identity("test")
    value = BoxedValue(1)

    assert store.load_value(vid) is None
    store.add(vid, value, vid.fingerprint)
    assert store.load_value(vid) == value
    assert store.get_fingerprint(vid) == vid.fingerprint


def test_persisted_store_memory_only_remove_works():
    store = PersistedStore.from_memory()

    vid = value_name_identity("test")
    value = BoxedValue(1)

    assert store.load_value(vid) is None
    store.add(vid, value, vid.fingerprint)
    assert store.load_value(vid) == value
    assert store.get_fingerprint(vid) == vid.fingerprint
    store.remove_vid(vid)
    assert store.load_value(vid) is None


def test_persisted_store_get_vids_works():
    store = PersistedStore.from_memory()

    vid = value_name_identity("test")
    value = BoxedValue(1)

    assert store.load_value(vid) is None
    store.add(vid, value, vid.fingerprint)

    assert store.get_vids() == {vid}


def test_persisted_store_get_metadata_works():
    store = PersistedStore.from_memory()

    vid = value_name_identity("test")
    value = BoxedValue(1)

    store.add(vid, value, vid.fingerprint)

    result_metadata = store.get_result_metadata(vid)
    assert result_metadata
    assert result_metadata.result_size == 54
    assert result_metadata.stored_size == 54
    assert result_metadata.save_duration > 0

    assert result_metadata.num_loads == 0
    assert result_metadata.total_load_durations == 0.0

    assert store.load_value(vid) == value

    assert result_metadata.num_loads == 1
    first_load_duration = result_metadata.total_load_durations
    assert first_load_duration > 0.0

    assert store.load_value(vid) == value
    assert result_metadata.num_loads == 2
    assert result_metadata.total_load_durations > first_load_duration


@pytest.mark.parametrize("size", [10, 1000])
def test_persisted_store_persists(size):
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        db_path = temp_storage_dir

        store = PersistedStore.from_file(db_path)

        vid = value_name_identity("test")
        value = BoxedValue("Hello World" * size)
        tag_name = "duck"

        assert store.load_value(vid) is None
        assert store.get_tag_vid(tag_name) is None

        store.add(vid, value, vid.fingerprint)
        store.tag(tag_name, vid)

        assert store.load_value(vid) == value
        assert store.get_fingerprint(vid) == vid.fingerprint
        assert store.get_tag_vid(tag_name) is vid

        store.close()

        store = PersistedStore.from_file(db_path)
        assert store.load_value(vid) == value
        assert store.get_fingerprint(vid) == vid.fingerprint
        assert store.get_tag_vid(tag_name) == vid

        store.close()


def test_persisted_store_persists_different_paths():
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        db_path = temp_storage_dir
        external_path = path.join(temp_storage_dir, "ext")
        mkdir(external_path)

        store = PersistedStore.from_file(db_path, external_path)

        vid = value_name_identity("test")
        value = list(range(100000))
        tag_name = "duck"

        assert store.load_value(vid) is None
        assert store.get_tag_vid(tag_name) is None

        store.add(vid, value, vid.fingerprint)
        store.tag(tag_name, vid)

        assert store.get_cached_value(vid).path == path.join(
            external_path, "test_builtins.list_0000000000.pickle"
        )
        assert store.get_fingerprint(vid) == vid.fingerprint
        assert store.get_tag_vid(tag_name) is vid

        store.close()

        print(temp_storage_dir)
        assert set(listdir(temp_storage_dir)) == {
            "mamo_store",
            "mamo_store.index",
            "mamo_store.lock",
            "mamo_store.tmp",
            "ext",
        }
        assert listdir(external_path) == ["test_builtins.list_0000000000.pickle"]


def test_persisted_store_unwraps_objproxies():
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        db_path = temp_storage_dir
        external_path = path.join(temp_storage_dir, "ext")
        mkdir(external_path)

        store = PersistedStore.from_file(db_path, external_path)

        vid = value_name_identity("test")
        value = ObjectProxy(list(range(100000)))
        tag_name = "duck"

        assert store.load_value(vid) is None

        store.add(vid, value, vid.fingerprint)

        assert store.get_cached_value(vid).path == path.join(
            external_path, "test_builtins.list_0000000000.pickle"
        )

        store.close()
