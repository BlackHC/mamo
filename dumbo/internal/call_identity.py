from dataclasses import dataclass
from dumbo.internal import function_identity, value_identity
from typing import Tuple


@dataclass
class CallIdentity:
    fid: function_identity.FunctionIdentity
    args_vid: Tuple[value_identity.ValueIdentity]
    kwargs_vid: Tuple[value_identity.ValueIdentity]


def identify_call(fid, args, kwargs):
    args_vid = tuple(value_identity.identify_value(arg) for arg in args)
    kwargs_vid = set((name, value_identity.identify_value(value)) for name, value in kwargs.items())

    return CallIdentity(fid, args_vid, kwargs_vid)