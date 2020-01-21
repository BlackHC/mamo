from mamo.internal import reflection

from mamo.internal.identities import (
    ValueFingerprintIdentity,
    ValueIdentity,
    CellIdentity,
    ValueCallIdentity,
    ValueCellResultIdentity
)
from mamo.internal.providers import IdentityProvider, ValueOracle


class IdentityRegistry(IdentityProvider):
    value_oracle: ValueOracle

    def __init__(self, value_oracle: ValueOracle):
        self.value_oracle = value_oracle

    def identify_call(self, fid, args, kwargs) -> ValueCallIdentity:
        args_vid = tuple(self.value_oracle.identify_value(arg) for arg in args)
        kwargs_vid = frozenset((name, self.value_oracle.identify_value(value)) for name, value in kwargs.items())

        return ValueCallIdentity(fid, args_vid, kwargs_vid)

    def identify_cell_result(self, cell_identity: CellIdentity, key: str) -> ValueCellResultIdentity:
        return ValueCellResultIdentity(cell_identity, key)

    def identify_value(self, value) -> ValueIdentity:
        fingerprint = self.value_oracle.fingerprint_value(value)
        return ValueFingerprintIdentity(reflection.get_type_qualified_name(value), fingerprint)
