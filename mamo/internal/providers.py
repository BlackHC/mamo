from abc import ABC
from types import FunctionType
from typing import NoReturn, Set

from mamo.internal.fingerprints import Fingerprint
from mamo.internal.identities import ValueIdentity, FunctionIdentity, CellIdentity


class FunctionProvider:
    def identify_function(self, function: FunctionType) -> FunctionIdentity:
        raise NotImplementedError()

    def identify_cell(self, name: str, cell_function: FunctionType) -> CellIdentity:
        raise NotImplementedError()

    def resolve_function(self, fid: FunctionIdentity) -> FunctionType:
        raise NotImplementedError()


class IdentityProvider:
    def identify_value(self, value) -> ValueIdentity:
        raise NotImplementedError()


class FingerprintProvider:
    def fingerprint_value(self, value):
        raise NotImplementedError()


class ValueOracle(IdentityProvider, FingerprintProvider, ABC):
    pass


class ValueProvider(ValueOracle, ABC):
    def resolve_value(self, vid: ValueIdentity) -> object:
        raise NotImplementedError()

    def resolve_fingerprint(self, vid: ValueIdentity) -> Fingerprint:
        raise NotImplementedError()

    def add(self, vid: ValueIdentity, value, fingerprint: Fingerprint) -> NoReturn:
        raise NotImplementedError()

    def remove_vid(self, vid: ValueIdentity) -> NoReturn:
        raise NotImplementedError()

    def remove_value(self, value: object) -> NoReturn:
        raise NotImplementedError()

    def has_vid(self, vid: ValueIdentity) -> bool:
        raise NotImplementedError()

    def has_value(self, value) -> bool:
        raise NotImplementedError()

    def get_vids(self) -> Set[ValueIdentity]:
        raise NotImplementedError()
