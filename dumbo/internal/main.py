from dumbo.internal import reflection
from functools import wraps

# Usually, Pythonistas don't like base classes. They know nothing.
from dumbo.internal.identities import ValueNameIdentity, ValueFingerprintIdentity, ValueCIDIdentity, FunctionIdentity, \
    CallIdentity, ValueIdentity
from dumbo.internal.online_cache import DumboOnlineCache
from dumbo.internal.persisted_cache import DumboPersistedCache
from dumbo.internal.return_handlers import wrap_return_value


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

        # TODO: move the hash registry etc to here?

        # We could support a generic fingerprint that uses the pickle protocol!
        fingerprint = reflection.try_get_value_fingerprint(value)
        if fingerprint is None:
            raise ValueError(f'Cannot fingerprint {value}!'
                             ' Please either add a plugin to support it,'
                             ' or register it with a name')

        return ValueFingerprintIdentity(
            reflection.get_type_qualified_name(value),
            fingerprint
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
            wrapped_result = wrap_return_value(result)
            self.online_cache.update(vid, wrapped_result)
            return wrapped_result

        return wrapped_func

    def register_value(self, value, unique_name):
        self.online_cache.update(ValueNameIdentity(unique_name), value)


dumbo: Dumbo = None


def init_dumbo(memory_only=True, path=None):
    global dumbo
    assert dumbo is None

    persisted_cache = DumboPersistedCache.from_memory() if memory_only else DumboPersistedCache.from_file(path)
    dumbo = Dumbo(persisted_cache)
