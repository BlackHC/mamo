from dataclasses import dataclass
from typing import Tuple, FrozenSet, Optional


MAX_FINGERPRINT_VALUE_LENGTH = 1024


class Fingerprint:
    pass


@dataclass(frozen=True)
class FingerprintDigest(Fingerprint):
    digest: object


@dataclass(frozen=True)
class FingerprintName(Fingerprint):
    name: str


@dataclass(frozen=True)
class FingerprintDigestRepr(FingerprintDigest):
    """`FingerprintDigest` that carries its original value to be more informative.

    For all purposes, we ignore the actual value for hashing and use the provided digest."""

    value: str

    def __eq__(self, other):
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


# We keep this separate from FunctionIdentity, so as to cache by identity
# and determine staleness using fingerprints.
# (Otherwise, we lack a key to index with and find stale entries.)
@dataclass(frozen=True)
class FunctionFingerprint(Fingerprint):
    fingerprint: object


# Includes dependencies.
@dataclass(frozen=True)
class DeepFunctionFingerprint(FunctionFingerprint):
    func_calls: FrozenSet[Tuple[Tuple[str, ...], FunctionFingerprint]]


class ResultFingerprint(Fingerprint):
    pass


@dataclass(frozen=True)
class CallFingerprint(ResultFingerprint):
    function: FunctionFingerprint
    # Need fingerprints everywhere! This needs to be a separate hierarchy!
    args: Tuple[Optional[Fingerprint], ...]
    kwargs: FrozenSet[Tuple[str, Optional[Fingerprint]]]


@dataclass(frozen=True)
class CellFingerprint:
    cell_code_fingerprint: FunctionFingerprint
    globals_load: FrozenSet[Tuple[Tuple[str, ...], Tuple["ValueIdentity", Fingerprint]]]
    outputs: FrozenSet[str]


@dataclass(frozen=True)
class CellResultFingerprint(ResultFingerprint):
    cell: CellFingerprint
    key: str


