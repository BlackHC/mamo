from dumbo.internal import reflection

from dumbo.internal.fingerprints import FingerprintProvider
from dumbo.internal.identities import (
    ValueFingerprintIdentity,
    ValueIdentity,
    CellIdentity,
    IdentityProvider,
    ValueCallIdentity,
    ValueCellResultIdentity
)


class IdentityRegistry(IdentityProvider):
    value_provider: IdentityProvider
    fingerprint_provider: FingerprintProvider

    def __init__(self, value_provider: IdentityProvider, fingerprint_provider: FingerprintProvider):
        self.value_provider = value_provider
        self.fingerprint_provider = fingerprint_provider

    def identify_call(self, fid, args, kwargs) -> ValueCallIdentity:
        args_vid = tuple(self.identify_value(arg) for arg in args)
        kwargs_vid = frozenset((name, self.identify_value(value)) for name, value in kwargs.items())

        return ValueCallIdentity(fid, args_vid, kwargs_vid)

    def identify_cell_result(self, cell_identity: CellIdentity, key: str) -> ValueCellResultIdentity:
        return ValueCellResultIdentity(cell_identity, key)

    def identify_value(self, value) -> ValueIdentity:
        vid = self.value_provider.identify_value(value)
        if vid is not None:
            return vid

        fingerprint = self.fingerprint_provider.fingerprint_value(value)
        return ValueFingerprintIdentity(reflection.get_type_qualified_name(value), fingerprint)
