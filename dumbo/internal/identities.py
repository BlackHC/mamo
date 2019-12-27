from dataclasses import dataclass
from typing import Tuple, FrozenSet, Generic, TypeVar, Optional

from dumbo.internal.fingerprints import Fingerprint, CallFingerprint, FingerprintName

T = TypeVar("T")


class ValueIdentity:
    def get_external_info(self):
        raise NotImplementedError()


@dataclass(frozen=True)
class ValueFingerprintIdentity(ValueIdentity):
    qualified_type_name: str
    fingerprint: Fingerprint

    def get_external_info(self):
        if isinstance(self.fingerprint, FingerprintName):
            return f"{self.fingerprint.name}"
        return f"{self.qualified_type_name}"


def value_name_identity(unique_name: str):
    return ValueFingerprintIdentity("{value}", FingerprintName(unique_name))


@dataclass(frozen=True)
class FunctionIdentity:
    qualified_name: str


@dataclass(frozen=True)
class CellIdentity(FunctionIdentity):
    """Cells don't have an identity beyond their code."""

    qualified_name: Optional[str]
    fingerprint: object


# TODO: merge this into CallIdentity?
@dataclass(frozen=True)
class ValueCallIdentity(ValueIdentity):
    fid: FunctionIdentity
    args_vid: Tuple[ValueIdentity, ...]
    kwargs_vid: FrozenSet[Tuple[str, ValueIdentity]]

    def get_external_info(self):
        # TODO: maybe convert get_external_info into a visitor pattern?
        # TODO: add tests that test all of this?

        # Look at arguments.
        # Do we have any named ones?
        args = []
        for arg in self.args_vid:
            args.append(arg.get_external_info())
        for name, value in self.kwargs_vid:
            args.append(f"{name}={value.get_external_info()}")
        if args:
            args = "_" + "_".join(args)
        else:
            args = ""
        return f"{self.fid.qualified_name}({args})"


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
