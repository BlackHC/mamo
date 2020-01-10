from os import mkdir, listdir, path

from dumbo.internal.identities import value_name_identity
from dumbo.internal.annotated_value import AnnotatedValue
from dumbo.internal.persisted_store import PersistedStore

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


def test_persisted_store_persists():
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        db_path = temp_storage_dir

        store = PersistedStore.from_file(db_path)

        vid = value_name_identity("test")
        value = BoxedValue(1)
        tag_name = "duck"

        assert store.load_value(vid) is None
        assert store.get_tag_vid(tag_name) is None

        store.add(vid, value, vid.fingerprint)
        store.tag(tag_name, vid)

        assert store.load_value(vid) == value
        assert store.get_fingerprint(vid) == vid.fingerprint
        assert store.get_tag_vid(tag_name) is vid

        store.testing_close()

        store = PersistedStore.from_file(db_path)
        assert store.load_value(vid) == value
        assert store.get_fingerprint(vid) == vid.fingerprint
        assert store.get_tag_vid(tag_name) == vid

        store.testing_close()


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

        store.testing_close()

        print(temp_storage_dir)
        assert set(listdir(temp_storage_dir)) == {
            "dumbo_store",
            "dumbo_store.index",
            "dumbo_store.lock",
            "dumbo_store.tmp",
            "ext",
        }
        assert listdir(external_path) == ["test_builtins.list_0000000000.pickle"]
