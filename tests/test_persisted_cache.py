from dumbo.internal.identities import ValueNameIdentity
from dumbo.internal.persisted_cache import DumboPersistedCache

from . import testing

import tempfile


def test_persisted_cache_memory_only():
    cache = DumboPersistedCache.from_memory()

    vid = ValueNameIdentity('test')
    value = testing.Value(1)

    assert cache.get_cached_value(vid) is None
    cache.update(vid, value)
    assert cache.get_cached_value(vid).value is value


def test_persisted_cache_persists():
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        db_path = temp_storage_dir + '/cache'

        cache = DumboPersistedCache.from_file(db_path)

        vid = ValueNameIdentity('test')
        value = testing.Value(1)
        tag_name = 'duck'

        assert cache.get_cached_value(vid) is None
        assert cache.get_tag_vid(tag_name) is None

        cache.update(vid, value)
        cache.tag(tag_name, vid)

        assert cache.get_cached_value(vid).value is value
        assert cache.get_tag_vid(tag_name) is vid

        cache.testing_close()

        cache = DumboPersistedCache.from_file(db_path)
        assert cache.get_cached_value(vid).value == value
        assert cache.get_tag_vid(tag_name) == vid

        cache.testing_close()
