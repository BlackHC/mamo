from types import FunctionType
from typing import Dict

from mamo.internal import reflection
from mamo.internal.identities import FunctionIdentity, CellIdentity
from mamo.internal.providers import FunctionProvider


class FunctionRegistry(FunctionProvider):
    fid_to_func: Dict[FunctionIdentity, FunctionType]

    def __init__(self):
        super().__init__()
        self.fid_to_func = {}

    def identify_function(self, func) -> FunctionIdentity:
        fid = FunctionIdentity(reflection.get_func_qualified_name(func))
        self.fid_to_func[fid] = func
        return fid

    def identify_cell(self, name: str, cell_function: FunctionType) -> CellIdentity:
        fid = CellIdentity(name)
        self.fid_to_func[fid] = cell_function
        return fid

    def resolve_function(self, fid):
        return self.fid_to_func.get(fid)
