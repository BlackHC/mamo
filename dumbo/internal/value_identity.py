from dataclasses import dataclass
from dumbo.internal.qualified_name import get_qualified_name
from dumbo.internal.state import dumbo_state
import hashlib


class ValueIdentity:
    pass


@dataclass
class ValueCIDIdentity:
    cid: object


@dataclass
class ValueFingerprintIdentity:
    qualified_type_name: str
    fingerprint: int


def get_type_qualified_name(value):
    return get_qualified_name(type(value))


# TODO can we link CIDs and fingerprints?
# TODO what about having a description identity/named identity for datasets?


def identify_value(value):
    cid = dumbo_state.get_value_cid(value)
    if cid is not None:
        return ValueCIDIdentity(cid)

    # TODO: gotta special-case lots of types here!!
    # At least numpy and torch?
    return ValueFingerprintIdentity(get_type_qualified_name(value), hashlib.md5(value))

