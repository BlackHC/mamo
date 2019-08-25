import dumbo.internal.persisted_cache
from dumbo.internal import state
import pytest

from .testing import DummyPersistedCache, Value


def test_doc_initial_update_works():
    persisted_cache = DummyPersistedCache()
    online_cache = state.DumboOnlineCache(persisted_cache)

    vid = state.ValueNameIdentity('test')
    value = Value(5)
    online_cache.update(vid, value)

    assert online_cache.get_value(vid) is value
    assert online_cache.get_vid(value) == vid


def test_doc_updating_value_works():
    persisted_cache = dumbo.internal.persisted_cache.DumboPersistedCache()
    online_cache = state.DumboOnlineCache(persisted_cache)

    vid = state.ValueNameIdentity('test')
    value1 = Value(5)
    online_cache.update(vid, value1)

    assert online_cache.get_value(vid) is value1
    assert online_cache.get_vid(value1) == vid

    value2 = Value(7)

    online_cache.update(vid, value2)
    assert online_cache.get_value(vid) is value2
    assert online_cache.get_vid(value2) == vid
    assert online_cache.get_vid(value1) is None


def test_doc_updating_same_value_throws():
    # Tt violates the "each call, different result" policy
    # TODO: add a custom exception type!
    persisted_cache = dumbo.internal.persisted_cache.DumboPersistedCache()
    online_cache = state.DumboOnlineCache(persisted_cache)

    vid = state.ValueNameIdentity('test')
    value = Value(5)
    online_cache.update(vid, value)

    assert online_cache.get_value(vid) is value
    assert online_cache.get_vid(value) == vid

    vid2 = state.ValueNameIdentity('test2')
    with pytest.raises(AttributeError):
        online_cache.update(vid2, value)
