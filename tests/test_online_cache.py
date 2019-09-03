import dumbo.internal.persisted_cache
import pytest

from dumbo.internal.identities import ValueNameIdentity, StoredValue
from dumbo.internal.online_cache import DumboOnlineCache

from .testing import DummyPersistedCache, BoxedValue


def test_doc_initial_update_works():
    persisted_cache = DummyPersistedCache()
    online_cache = DumboOnlineCache(persisted_cache)

    vid = ValueNameIdentity('test')
    value = StoredValue(BoxedValue(5))
    online_cache.update(vid, value)

    assert online_cache.get_stored_value(vid) is value
    assert online_cache.get_vid(value.value) == vid


def test_doc_updating_value_works():
    persisted_cache = DummyPersistedCache()
    online_cache = DumboOnlineCache(persisted_cache)

    vid = ValueNameIdentity('test')
    value1 = StoredValue(BoxedValue(5))
    online_cache.update(vid, value1)

    assert online_cache.get_stored_value(vid) is value1
    assert online_cache.get_vid(value1.value) == vid

    value2 = StoredValue(BoxedValue(7))

    online_cache.update(vid, value2)
    assert online_cache.get_stored_value(vid) is value2
    assert online_cache.get_vid(value2.value) == vid
    assert online_cache.get_vid(value1.value) is None


def test_doc_updating_same_value_throws():
    # Tt violates the "each call, different result" policy
    # TODO: add a custom exception type!
    persisted_cache = DummyPersistedCache()
    online_cache = DumboOnlineCache(persisted_cache)

    vid = ValueNameIdentity('test')
    value = StoredValue(BoxedValue(5))
    online_cache.update(vid, value)

    assert online_cache.get_stored_value(vid) is value
    assert online_cache.get_vid(value.value) == vid

    vid2 = ValueNameIdentity('test2')
    with pytest.raises(AttributeError):
        online_cache.update(vid2, value)


def test_doc_tagging_works():
    persisted_cache = DummyPersistedCache()
    online_cache = DumboOnlineCache(persisted_cache)

    vid = ValueNameIdentity('test')
    value = StoredValue(BoxedValue(5))
    tag_name = 'quack'

    online_cache.update(vid, value)
    online_cache.tag(tag_name, vid)

    assert online_cache.get_stored_value(vid) is value
    assert online_cache.get_vid(value.value) == vid
    assert online_cache.get_tag_stored_value(tag_name) is value