from dataclasses import dataclass
from types import FunctionType
from typing import Tuple, FrozenSet, Generic, TypeVar, Dict, Optional

from dumbo.internal.fingerprints import Fingerprint, CallFingerprint

T = TypeVar("T")


class ValueIdentity:
    def get_external_info(self):
        raise NotImplementedError()


# TODO: replace ValueNameIdentity with ValueFingerprintIdentity(FingerprintName)!
@dataclass(frozen=True)
class ValueNameIdentity(ValueIdentity):
    unique_name: str

    def get_external_info(self):
        return self.unique_name


@dataclass(frozen=True)
class ValueFingerprintIdentity(ValueIdentity):
    qualified_type_name: str
    fingerprint: Fingerprint

    def get_external_info(self):
        return f"{self.qualified_type_name}_{self.fingerprint}"


@dataclass(frozen=True)
class FunctionIdentity:
    qualified_name: str


@dataclass(frozen=True)
class CellIdentity(FunctionIdentity):
    """Cells don't have an identity beyond their code."""
    qualified_name: Optional[str]
    fingerprint: object


@dataclass(frozen=True)
class CallIdentity:
    fid: FunctionIdentity
    args_vid: Tuple[ValueIdentity, ...]
    kwargs_vid: FrozenSet[Tuple[str, ValueIdentity]]


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
    fingerprint: Fingerprint


# This is kept by online and persistent cache and might later include more debug info.
@dataclass
class StoredResult(StoredValue[T]):
    fingerprint: CallFingerprint


class IdentityProvider:
    def identify_value(self, value):
        raise NotImplementedError()

    def resolve_function(self, fid: FunctionIdentity):
        raise NotImplementedError()

