from abc import ABC
from dataclasses import dataclass
from typing import Tuple, FrozenSet

from mamo.internal.fingerprints import Fingerprint, FingerprintName


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
    pass


class ComputedValueIdentity(ValueIdentity, ABC):
    pass


# TODO: merge this into CallIdentity?
@dataclass(frozen=True)
class ValueCallIdentity(ComputedValueIdentity):
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
            args = ",".join(args)
        else:
            args = ""
        return f"{self.fid.qualified_name}({args})"


@dataclass(frozen=True)
class ValueCellResultIdentity(ComputedValueIdentity):
    cell: CellIdentity
    key: str

    def get_external_info(self):
        return f"cell_{self.cell.name}.{self.key}"


class ValueIdentityVisitor:
    def visit_fingerprint(self, vid: ValueFingerprintIdentity):
        raise TypeError(f"{type(vid)} not supported! (for {vid})")

    def visit_call(self, vid: ValueCallIdentity):
        raise TypeError(f"{type(vid)} not supported! (for {vid})")

    def visit_cell_result(self, vid: ValueCellResultIdentity):
        raise TypeError(f"{type(vid)} not supported! (for {vid})")

    def visit_computed_value(self, vid: ComputedValueIdentity):
        raise TypeError(f"{type(vid)} not supported! (for {vid})")

    def visit(self, vid: ValueIdentity):
        if isinstance(vid, ValueFingerprintIdentity):
            return self.visit_fingerprint(vid)
        elif isinstance(vid, ValueCallIdentity):
            return self.visit_call(vid)
        elif isinstance(vid, ValueCellResultIdentity):
            return self.visit_cell_result(vid)
        elif isinstance(vid, ComputedValueIdentity):
            return self.visit_computed_value(vid)
        raise NotImplementedError(f"Unknown type {type(vid)} for {vid}")
