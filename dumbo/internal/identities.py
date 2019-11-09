from dataclasses import dataclass
from typing import Tuple, FrozenSet, Optional, Generic, TypeVar


T = TypeVar("T")

# TODO: can we freeze the fields? (and not use unsafe_hash=True)?


class ValueIdentity:
    def get_external_info(self):
        raise NotImplementedError()


@dataclass(unsafe_hash=True)
class ValueNameIdentity(ValueIdentity):
    unique_name: str

    def get_external_info(self):
        return self.unique_name


@dataclass(unsafe_hash=True)
class FingerprintDigest:
    digest: object


@dataclass(unsafe_hash=False)
class FingerprintDigestValue(FingerprintDigest):
    """`FingerprintDigest that carries its original value to be more informative."""
    value: object

    def __eq__(self, other):
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


@dataclass(unsafe_hash=True)
class ValueFingerprintIdentity(ValueIdentity):
    qualified_type_name: str
    fingerprint: FingerprintDigest

    def get_external_info(self):
        return f"{self.qualified_type_name}_{self.fingerprint}"


@dataclass(unsafe_hash=True)
class FunctionIdentity:
    qualified_name: str


@dataclass(unsafe_hash=True)
class CellIdentity(FunctionIdentity):
    fingerprint: object


# We keep this separate from FunctionIdentity, so as to cache by identity
# and determine staleness using fingerprints.
# (Otherwise, we lack a key to index with.)
@dataclass(unsafe_hash=True)
class FunctionFingerprint:
    fingerprint: object


# Runtime dependencies.
@dataclass(unsafe_hash=True)
class DeepFunctionFingerprint(FunctionFingerprint):
    global_loads: FrozenSet[Tuple[Tuple[str, ...], ValueIdentity]]
    func_calls: FrozenSet[Tuple[Tuple[str, ...], Optional[Tuple[FunctionIdentity, FunctionFingerprint]]]]


@dataclass(unsafe_hash=True)
class CallIdentity:
    fid: FunctionIdentity
    args_vid: Tuple[ValueIdentity, ...]
    kwargs_vid: FrozenSet[Tuple[str, ValueIdentity]]


@dataclass(unsafe_hash=True)
class CallFingerprint:
    function: FunctionFingerprint
    args: Tuple[Optional["CallFingerprint"]]
    kwargs: FrozenSet[Tuple[str, Optional["CallFingerprint"]]]


# TODO: merge this into CallIdentity?
@dataclass(unsafe_hash=True)
class ValueCIDIdentity(ValueIdentity):
    cid: CallIdentity

    def get_external_info(self):
        # TODO: maybe convert get_external_info into a vistor pattern?

        # Look at arguments.
        # Do we have any named ones?
        args = []
        for arg in self.cid.args_vid:
            if isinstance(arg, ValueNameIdentity):
                args.append(arg.get_external_info())
        for name, value in self.cid.kwargs_vid:
            if isinstance(value, ValueNameIdentity):
                args.append(f"{name}_{value.get_external_info()}")
        if args:
            args = "_" + "_".join(args)
        else:
            args = ""
        return f"{self.cid.fid.qualified_name}{args}"


@dataclass
class StoredValue(Generic[T]):
    value: T


# This is kept by online and persistent cache and might later include more debug info.
@dataclass
class StoredResult(StoredValue[T]):
    value: T
    call_fingerprint: CallFingerprint
