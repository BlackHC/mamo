from dataclasses import dataclass
from typing import Tuple, FrozenSet

from persistent import Persistent


class ValueIdentity(Persistent):
    def get_external_info(self):
        raise NotImplementedError()


@dataclass(unsafe_hash=True)
class ValueNameIdentity(ValueIdentity):
    unique_name: str

    def get_external_info(self):
        return self.unique_name


@dataclass(unsafe_hash=True)
class ValueFingerprintIdentity(ValueIdentity):
    qualified_type_name: str
    fingerprint: int

    def get_external_info(self):
        return f"{self.qualified_type_name}_{self.fingerprint}"


@dataclass(unsafe_hash=True)
class FunctionIdentity(Persistent):
    qualified_name: str
    hashed_code: int


@dataclass(unsafe_hash=True)
class CallIdentity(Persistent):
    fid: FunctionIdentity
    args_vid: Tuple[ValueIdentity, ...]
    kwargs_vid: FrozenSet[Tuple[str, ValueIdentity]]


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



