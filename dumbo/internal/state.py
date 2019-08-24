from dataclasses import dataclass
from typing import Tuple, Set
from dumbo.internal import reflection
from persistent import Persistent
from persistent.mapping import PersistentMapping
from functools import wraps


UNKNOWN = object


# Usually, Pythonistas don't like base classes. They know nothing.
class ValueIdentity(Persistent):
    pass


@dataclass(unsafe_hash=True)
class ValueNameIdentity(ValueIdentity):
    unique_name: str


@dataclass(unsafe_hash=True)
class ValueFingerprintIdentity(ValueIdentity):
    qualified_type_name: str
    fingerprint: int


@dataclass(unsafe_hash=True)
class ValueCIDIdentity(ValueIdentity):
    cid: 'CallIdentity'


@dataclass(unsafe_hash=True)
class FunctionIdentity(Persistent):
    qualified_name: str
    hashed_code: int


@dataclass(unsafe_hash=True)
class CallIdentity(Persistent):
    fid: FunctionIdentity
    args_vid: Tuple[ValueIdentity, ...]
    kwargs_vid: Set[Tuple[str, ValueIdentity]]


class CachedValue(Persistent):
    pass


@dataclass(unsafe_hash=True)
class ExternallyCachedValue(CachedValue):
    path: str

    def load(self):
        return None


@dataclass(unsafe_hash=True)
class DBCachedValue(CachedValue):
    value: object


# TODO: to repr method
class DumboPersistedCache(Persistent):
    vid_to_cached_value: PersistentMapping

    def __init__(self):
        self.vid_to_cached_value = PersistentMapping()

    def update(self, vid, value):
        self.vid_to_cached_value[vid] = value

    def get_cached_value(self, vid):
        return self.vid_to_cached_value.get(vid, None)


# TODO: to repr method
class DumboOnlineCache:
    persisted_cache: DumboPersistedCache
    vid_to_value: dict
    value_to_vid: dict

    def __init__(self, persisted_cache):
        self.vid_to_value = {}
        self.value_to_vid = {}
        self.persisted_cache = persisted_cache

    def try_load_cached_value(self, vid):
        cached_value = self.persisted_cache.get_cached_value(vid)
        if cached_value is None:
            return UNKNOWN

        # Load value
        if isinstance(cached_value, DBCachedValue):
            value = cached_value.value
        else:
            raise TypeError(f"Handling of {cached_value} not implemented yet!")
        return value

    def get_value(self, vid):
        if vid in self.vid_to_value:
            return self.vid_to_value[vid]

        value = self.try_load_cached_value(vid)
        if value is not UNKNOWN:
            # Cache the value in the online layer.
            self.vid_to_value[vid] = value
            self.value_to_vid[id(value)] = vid

        return value

    def get_vid(self, value):
        return self.value_to_vid.get(id(value))

    def update(self, vid, value):
        # This is a transactional function that first error-checks/validates and
        # only then performs mutations.
        # This can still fail to be atomic because of bugs
        # but not because of invalid parameters.

        # Validation checks:
        existing_value = UNKNOWN
        if vid in self.vid_to_value:
            existing_value = self.vid_to_value[vid]
            if existing_value is value:
                return

        existing_vid = self.value_to_vid.get(id(value))
        if existing_vid is not None:
            if existing_vid is not vid:
                # ERROR: Value has already been linked to another vid.
                # TODO: support handlers to create views/proxies on existing results.
                raise AttributeError(
                    f"{vid} has same value as {existing_vid}!"
                    "We follow a \"each computation, different result\" policy."
                    "This makes tracking possible."
                )

        # Now perform changes:
        # Unlink existing value.
        if existing_value is not UNKNOWN:
            del self.value_to_vid[id(existing_value)]

        if existing_vid is None:
            self.value_to_vid[id(value)] = vid

        self.vid_to_value[vid] = value

        # TODO: Update in the persisted layer, too.
        # Decision logic for how to store/cache a value!
        # And which values we can even cache!
        # (Ie no Fingerprint ones and Name Identities probs!)


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

    def _identify_value(self, value):
        # TODO can we link CIDs and fingerprints?
        # TODO what about having a description identity/named identity for datasets?
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

            memoized_result = self._get_value(vid)
            if memoized_result is not UNKNOWN:
                return memoized_result

            result = func(*args, **kwargs)
            # TODO: we might want to keep multiple results for stochastic operations
            self.online_cache.update(vid, result)
            return result

        return wrapped_func

    def register_value(self, value, unique_name):
        self.online_cache.update(ValueNameIdentity(unique_name), value)


dumbo: Dumbo = None


def init_dumbo():
    global dumbo
    assert dumbo is None
    # TODO: add database connection and commits
    dumbo = Dumbo(DumboPersistedCache())
