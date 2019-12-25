from dataclasses import dataclass
from typing import Tuple, FrozenSet, Optional, Generic, TypeVar


T = TypeVar("T")


class ValueIdentity:
    def get_external_info(self):
        raise NotImplementedError()


@dataclass(frozen=True)
class ValueNameIdentity(ValueIdentity):
    unique_name: str

    def get_external_info(self):
        return self.unique_name


@dataclass(frozen=True)
class FingerprintDigest:
    digest: object


@dataclass(frozen=True)
class FingerprintDigestValue(FingerprintDigest):
    """`FingerprintDigest` that carries its original value to be more informative.

    For all purposes, we ignore the actual value for hashing and use the provided digest."""
    value: object

    def __eq__(self, other):
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


@dataclass(frozen=True)
class ValueFingerprintIdentity(ValueIdentity):
    qualified_type_name: str
    fingerprint: FingerprintDigest

    def get_external_info(self):
        return f"{self.qualified_type_name}_{self.fingerprint}"


@dataclass(frozen=True)
class FunctionIdentity:
    qualified_name: str


@dataclass(frozen=True)
class CellIdentity(FunctionIdentity):
    """Cells don't have an identity beyond their code."""
    fingerprint: object


# We keep this separate from FunctionIdentity, so as to cache by identity
# and determine staleness using fingerprints.
# (Otherwise, we lack a key to index with and find stale entries.)
@dataclass(frozen=True)
class FunctionFingerprint:
    fingerprint: object


# Includes dependencies.
@dataclass(frozen=True)
class DeepFunctionFingerprint(FunctionFingerprint):
    global_loads: FrozenSet[Tuple[Tuple[str, ...], ValueIdentity]]
    func_calls: FrozenSet[Tuple[Tuple[str, ...], Optional[Tuple[FunctionIdentity, FunctionFingerprint]]]]


@dataclass(frozen=True)
class CallIdentity:
    fid: FunctionIdentity
    args_vid: Tuple[ValueIdentity, ...]
    kwargs_vid: FrozenSet[Tuple[str, ValueIdentity]]


@dataclass(frozen=True)
class CallFingerprint:
    function: FunctionFingerprint
    # Need fingerprints everywhere! This needs to be a separate hierarchy!
    args: Tuple[Optional["CallFingerprint"]]
    kwargs: FrozenSet[Tuple[str, Optional["CallFingerprint"]]]


# TODO: merge this into CallIdentity?
@dataclass(frozen=True)
class ValueCIDIdentity(ValueIdentity):
    cid: CallIdentity

    def get_external_info(self):
        # TODO: maybe convert get_external_info into a visitor pattern?

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
