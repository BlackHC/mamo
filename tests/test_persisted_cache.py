from os import mkdir, listdir, path

from dumbo.internal.identities import ValueNameIdentity, StoredResult
from dumbo.internal.persisted_cache import DumboPersistedCache

from . import testing

import tempfile


def test_persisted_cache_memory_only():
    cache = DumboPersistedCache.from_memory()

    vid = ValueNameIdentity("test")
    value = StoredResult(testing.BoxedValue(1), None)

    assert cache.get_cached_value(vid) is None
    cache.update(vid, value)
    assert cache.get_cached_value(vid).value.cached_value is value.value


def test_persisted_cache_persists():
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        db_path = temp_storage_dir

        cache = DumboPersistedCache.from_file(db_path)

        vid = ValueNameIdentity("test")
        value = StoredResult(testing.BoxedValue(1), None)
        tag_name = "duck"

        assert cache.get_cached_value(vid) is None
        assert cache.get_tag_vid(tag_name) is None

        cache.update(vid, value)
        cache.tag(tag_name, vid)

        assert cache.get_cached_value(vid).value.cached_value is value.value
        assert cache.get_tag_vid(tag_name) is vid

        cache.testing_close()

        cache = DumboPersistedCache.from_file(db_path)
        assert cache.get_cached_value(vid).value.cached_value == value.value
        assert cache.get_tag_vid(tag_name) == vid

        cache.testing_close()


def test_persisted_cache_persists_different_paths():
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        db_path = temp_storage_dir
        external_path = path.join(temp_storage_dir, "ext")
        mkdir(external_path)

        cache = DumboPersistedCache.from_file(db_path, external_path)

        vid = ValueNameIdentity("test")
        value = StoredResult(list(range(100000)), None)
        tag_name = "duck"

        assert cache.get_cached_value(vid) is None
        assert cache.get_tag_vid(tag_name) is None

        cache.update(vid, value)
        cache.tag(tag_name, vid)

        assert cache.get_cached_value(vid).value.path == path.join(
            external_path, "test_builtins.list_0000000000.pickle"
        )
        assert cache.get_tag_vid(tag_name) is vid

        cache.testing_close()

        print(temp_storage_dir)
        assert set(listdir(temp_storage_dir)) == {
            "dumbo_persisted_cache",
            "dumbo_persisted_cache.index",
            "dumbo_persisted_cache.lock",
            "dumbo_persisted_cache.tmp",
            "ext",
        }
        assert listdir(external_path) == ["test_builtins.list_0000000000.pickle"]
