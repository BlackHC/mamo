from types import FunctionType
from typing import Dict

from dumbo.internal import reflection

from dumbo.internal.fingerprints import FingerprintProvider
from dumbo.internal.identities import (
    ValueFingerprintIdentity,
    FunctionIdentity,
    CallIdentity,
    ValueIdentity,
    CellIdentity,
    IdentityProvider)
from dumbo.internal.online_cache import DumboOnlineCache


class IdentityRegistry(IdentityProvider):
    online_cache: DumboOnlineCache
    fingerprint_provider: FingerprintProvider

    fid_to_func: Dict[FunctionIdentity, FunctionType]

    def __init__(self, online_cache: DumboOnlineCache, fingerprint_provider: FingerprintProvider):
        self.online_cache = online_cache
        self.fingerprint_provider = fingerprint_provider

        self.fid_to_func = {}

    def resolve_function(self, fid):
        return self.fid_to_func.get(fid)

    def identify_function(self, func) -> FunctionIdentity:
        fid = FunctionIdentity(reflection.get_func_qualified_name(func))
        self.fid_to_func[fid] = func
        return fid

    def identify_cell(self, name: str, cell_function: FunctionType) -> FunctionIdentity:
        if name is not None:
            fid = CellIdentity(name, None)
        else:
            fid = CellIdentity(None, reflection.get_func_fingerprint(cell_function))
        self.fid_to_func[fid] = cell_function
        return fid

    def identify_call(self, fid, args, kwargs) -> CallIdentity:
        args_vid = tuple(self.identify_value(arg) for arg in args)
        kwargs_vid = frozenset((name, self.identify_value(value)) for name, value in kwargs.items())

        return CallIdentity(fid, args_vid, kwargs_vid)

    def identify_value(self, value) -> ValueIdentity:
        vid = self.online_cache.get_vid(value)
        if vid is not None:
            return vid

        fingerprint = self.fingerprint_provider.fingerprint_value(value)
        return ValueFingerprintIdentity(reflection.get_type_qualified_name(value), fingerprint)
