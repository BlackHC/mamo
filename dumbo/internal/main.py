from dumbo.internal import reflection
from functools import wraps

# Usually, Pythonistas don't like base classes. They know nothing.
from dumbo.internal.identities import ValueNameIdentity, ValueFingerprintIdentity, ValueCIDIdentity, FunctionIdentity, \
    CallIdentity, ValueIdentity
from dumbo.internal.online_cache import DumboOnlineCache
from dumbo.internal.persisted_cache import DumboPersistedCache


class Dumbo:
    online_cache: DumboOnlineCache
    persisted_cache: DumboPersistedCache

    def __init__(self, persisted_cache):
        self.persisted_cache = persisted_cache
        self.online_cache = DumboOnlineCache(persisted_cache)

    def _get_value(self, vid):
        return self.online_cache.get_value(vid)

    def _get_vid(self, value):
        return self.online_cache.get_vid(value)

    def _identify_function(self, func):
        return FunctionIdentity(
            reflection.get_func_qualified_name(func),
            reflection.get_func_hash(func)
        )

    def _identify_call(self, fid, args, kwargs):
        args_vid = tuple(self._identify_value(arg) for arg in args)
        kwargs_vid = frozenset((name, self._identify_value(value)) for name, value in kwargs.items())

        return CallIdentity(fid, args_vid, kwargs_vid)

    def _identify_value(self, value) -> ValueIdentity:
        vid = self._get_vid(value)
        if vid is not None:
            return vid

        # TODO: gotta special-case lots of types here!!
        # At least numpy and torch?
        return ValueFingerprintIdentity(
            reflection.get_type_qualified_name(value),
            reflection.get_value_hash(value)
        )

    def wrap_function(self, func):
        fid = self._identify_function(func)

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            cid = self._identify_call(fid, args, kwargs)
            vid = ValueCIDIdentity(cid)

            # TODO: logic about whether to load from cache or recompute!
            memoized_result = self._get_value(vid)
            if memoized_result is not None:
                return memoized_result

            result = func(*args, **kwargs)
            # TODO: we might want to keep multiple results for stochastic operations
            self.online_cache.update(vid, result)
            return result

        return wrapped_func

    def register_value(self, value, unique_name):
        self.online_cache.update(ValueNameIdentity(unique_name), value)


dumbo: Dumbo = None


def init_dumbo(memory_only=True, path=None):
    global dumbo
    assert dumbo is None

    persisted_cache = DumboPersistedCache.from_memory() if memory_only else DumboPersistedCache.from_file(path)
    dumbo = Dumbo(persisted_cache)
