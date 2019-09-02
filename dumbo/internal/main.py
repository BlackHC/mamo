from typing import Optional

from dumbo.internal import reflection
from functools import wraps

# Usually, Pythonistas don't like base classes. They know nothing.
from dumbo.internal.identities import ValueNameIdentity, ValueFingerprintIdentity, ValueCIDIdentity, FunctionIdentity, \
    CallIdentity, ValueIdentity
from dumbo.internal.module_extension import MODULE_EXTENSIONS
from dumbo.internal.online_cache import DumboOnlineCache
from dumbo.internal.persisted_cache import DumboPersistedCache

from dumbo.internal import default_module_extension


# Install the default module extension.
MODULE_EXTENSIONS.default_extension = default_module_extension.DefaultModuleExtension()


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

    def _identify_function(self, func) -> FunctionIdentity:
        return FunctionIdentity(
            reflection.get_func_qualified_name(func),
            reflection.get_func_hash(func)
        )

    def _identify_call(self, fid, args, kwargs) -> CallIdentity:
        args_vid = tuple(self._identify_value(arg) for arg in args)
        kwargs_vid = frozenset((name, self._identify_value(value)) for name, value in kwargs.items())

        return CallIdentity(fid, args_vid, kwargs_vid)

    def _identify_value(self, value) -> ValueIdentity:
        vid = self._get_vid(value)
        if vid is not None:
            return vid

        fingerprint = MODULE_EXTENSIONS.compute_fingerprint(value)

        if fingerprint is None:
            raise ValueError(f'Cannot fingerprint {value}!'
                             ' Please either add an extension to support it,'
                             ' or register it with a name')

        return ValueFingerprintIdentity(
            reflection.get_type_qualified_name(value),
            fingerprint
        )

    @staticmethod
    def wrap_function(func):
        # This method is a static method, so that dumbo does not need to be initialized.
        fid = dumbo._identify_function(func) if dumbo is not None else None

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            nonlocal fid

            # If dumbo was not initialized before, we might still have to set fid.
            if fid is None:
                # Just initialize it with defaults.
                if dumbo is None:
                    # TODO: maybe log?
                    init_dumbo()

                fid = dumbo._identify_function(func)

            cid = dumbo._identify_call(fid, args, kwargs)
            vid = ValueCIDIdentity(cid)

            # TODO: logic about whether to load from cache or recompute!
            memoized_result = dumbo._get_value(vid)
            if memoized_result is not None:
                return memoized_result

            result = func(*args, **kwargs)
            wrapped_result = MODULE_EXTENSIONS.wrap_return_value(result)
            dumbo.online_cache.update(vid, wrapped_result)
            return wrapped_result

        return wrapped_func

    def register_external_value(self, unique_name, value):
        # TODO: add an error here if value already exists within the cache.
        self.online_cache.update(ValueNameIdentity(unique_name), value)

    def tag(self, tag_name, value):
        # Value should exist in the cache.
        if value is not None:
            if not self.online_cache.has_value(value):
                raise ValueError('Value has not been registered previously!')
            # Register value
            self.online_cache.tag(tag_name, self.online_cache.get_vid(value))
        else:
            self.online_cache.tag(tag_name, None)


    def get_tag_value(self, tag_name):
        return self.online_cache.get_tag_value(tag_name)

    def get_external_value(self, unique_name):
        return self._get_value(ValueNameIdentity(unique_name))

    def testing_close(self):
        self.persisted_cache.testing_close()


dumbo: Optional[Dumbo] = None


def init_dumbo(memory_only=True, path=None):
    global dumbo
    assert dumbo is None

    persisted_cache = DumboPersistedCache.from_memory() if memory_only else DumboPersistedCache.from_file(path)
    dumbo = Dumbo(persisted_cache)
