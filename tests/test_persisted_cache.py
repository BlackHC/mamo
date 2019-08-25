from dumbo.internal import persisted_cache
from dumbo.internal import state

from . import testing

import tempfile


def test_persisted_cache_memory_only():
    cache = persisted_cache.DumboPersistedCache.from_memory()

    vid = state.ValueNameIdentity('test')
    value = testing.Value(1)

    assert cache.get_cached_value(vid) is None
    cache.update(vid, value)
    assert cache.get_cached_value(vid).value is value


def test_persisted_cache_persists():
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        db_path = temp_storage_dir + '/cache'

        cache = persisted_cache.DumboPersistedCache.from_file(db_path)

        vid = state.ValueNameIdentity('test')
        value = testing.Value(1)

        assert cache.get_cached_value(vid) is None
        cache.update(vid, value)
        assert cache.get_cached_value(vid).value is value

        cache.db.close()

        cache = persisted_cache.DumboPersistedCache.from_file(db_path)
        assert cache.get_cached_value(vid).value == value

        cache.db.close()
