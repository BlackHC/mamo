import dis
import hashlib
import inspect
import marshal
from dataclasses import dataclass
from types import FunctionType, CodeType
import builtins

# Bytecode-extracted features. Independent of runtime and can be cached.
from typing import FrozenSet, Tuple, Optional, List, Set


@dataclass(frozen=True)
class FunctionDependencies:
    global_loads: FrozenSet[Tuple[str, ...]]
    global_stores: FrozenSet[str]
    func_calls: FrozenSet[Tuple[str, ...]]


def get_module_name(value):
    return value.__class__.__module__


def _get_qualified_name(func):
    # TODO: handle Jupyter notebooks?
    # In notebooks, __module__ will be "__main__".
    return f"{func.__module__}.{func.__qualname__}"


def get_type_qualified_name(value):
    return _get_qualified_name(type(value))


def get_func_qualified_name(func):
    return _get_qualified_name(func)


@dataclass
class CodeAnalyzer:
    instructions: List[dis.Instruction]
    index: int = 0

    def get_argval(self):
        return self.instructions[self.index].argval

    def check_opnames(self, *opnames):
        return self.instructions[self.index].opname in opnames

    def nest(self):
        return CodeAnalyzer(self.instructions, self.index)

    def unroll_op_stack(self, remainder_stacksize):
        instruction = self.instructions[self.index]
        # + 1 as we ignore the return value that will be pushed onto the stack.
        stack_size = 1 - dis.stack_effect(instruction.opcode, instruction.arg)

        self.index -= 1

        while self.index >= 0 and stack_size > remainder_stacksize:
            instruction = self.instructions[self.index]
            stack_size -= dis.stack_effect(instruction.opcode, instruction.arg)
            self.index -= 1

        return self

    def unroll_load(self, reversed_qualified_name):
        while self.index >= 0:
            instruction = self.instructions[self.index]
            if instruction.opname == "LOAD_GLOBAL":
                reversed_qualified_name.append(instruction.argval)
                return tuple(reversed(reversed_qualified_name))
            elif instruction.opname == "LOAD_ATTR":
                reversed_qualified_name.append(instruction.argval)
            else:
                break
            self.index -= 1

        # TODO: log?
        return None

    def unroll_load_method(self):
        if self.check_opnames('LOAD_METHOD'):
            qualified_name = [self.get_argval()]
            self.index -= 1
            qualified_name = self.unroll_load(qualified_name)
            return qualified_name

    def try_parse_load(self, global_loads):
        instruction = self.instructions[self.index]
        if instruction.opname == "LOAD_GLOBAL":
            qualified_name = [instruction.argval]

            # Now try to resolve attribute accesses.
            while self.index <= len(self.instructions):
                self.index += 1
                instruction = self.instructions[self.index]
                if instruction.opname in ("LOAD_ATTR", "LOAD_METHOD"):
                    qualified_name.append(instruction.argval)
                else:
                    break

            global_loads.add(tuple(qualified_name))
            return True

        return False

    def try_parse_call(self, called_funcs: Set[Tuple[str, ...]]):
        if self.check_opnames("CALL_FUNCTION", "CALL_FUNCTION_KW", "CALL_FUNCTION_EX"):
            qualified_name = self.nest().unroll_op_stack(1).unroll_load([])
            if qualified_name is not None:
                called_funcs.add(qualified_name)

            self.index += 1
            return True
        elif self.check_opnames('CALL_METHOD'):
            qualified_name = self.nest().unroll_op_stack(2).unroll_load_method()
            if qualified_name is not None:
                called_funcs.add(qualified_name)

            self.index += 1
            return True
        return False

    def try_parse_store(self, global_stores: Set[str]):
        if self.check_opnames("STORE_GLOBAL"):
            global_stores.add(self.get_argval())
            self.index += 1
            return True
        return False

    def analyze(self):
        called_funcs = set()
        global_stores = set()
        global_loads = set()

        while self.index < len(self.instructions):
            if self.try_parse_load(global_loads):
                pass
            elif self.try_parse_store(global_stores):
                pass
            elif self.try_parse_call(called_funcs):
                pass
            else:
                self.index += 1

        return FunctionDependencies(frozenset(global_loads), frozenset(global_stores), frozenset(called_funcs))

    @staticmethod
    def from_func_or_code(func_or_code: FunctionType):
        instructions = list(dis.get_instructions(func_or_code))
        return CodeAnalyzer(instructions)


def get_code_object_fingerprint(code_object: CodeType):
    # TODO: add cache?
    hash_method = hashlib.md5(code_object.co_code)
    # This seems to only output stable objects for version==2!
    hash_method.update(marshal.dumps(code_object.co_consts, 2))
    return hash_method.digest()


def get_func_fingerprint(func: FunctionType):
    return get_code_object_fingerprint(func.__code__)


def resolve_qualified_name(qualified_name: Tuple[str, ...], namespace: dict):
    resolved = namespace.get(qualified_name[0])
    for attr in qualified_name[1:]:
        if resolved is None:
            break
        resolved = getattr(resolved, attr)
    return resolved


def resolve_qualified_names(qualified_names: FrozenSet[Tuple[str, ...]], namespace: dict):
    resolved_dict = {}
    for qualified_name in qualified_names:
        resolved_dict[qualified_name] = resolve_qualified_name(qualified_name, namespace)
    return resolved_dict


def get_func_deps(func: FunctionType) -> FunctionDependencies:
    # We can cache the globals dependencies and the code hash.
    # Then we need to create fingerprints for all referenced global values
    # And figure out whether we want to include dependencies for functions that are being
    # called.

    deps = CodeAnalyzer.from_func_or_code(func).analyze()

    loads = {load for load in deps.global_loads if load[0] not in deps.global_stores}
    calls = {call for call in deps.func_calls if call[0] not in deps.global_stores}

    loads.difference_update(calls)

    return FunctionDependencies(frozenset(loads), frozenset(deps.global_stores), frozenset(calls))


def is_func_local(func, local_prefix: Optional[str]):
    module = inspect.getmodule(func)
    if module is None:
        # TODO: log? this is weird
        return True

    # Functions in the main module are local by nature (so we don't need a local_prefix to establish that).
    if module.__name__ == "__main__":
        return True

    if local_prefix is None:
        return False

    # Python's builtin module does not have a __file__ field.
    if not hasattr(module, "__file__"):
        return False

    return module.__file__.startswith(local_prefix)


def is_func_builtin(func):
    if inspect.isbuiltin(func):
        return True
    if inspect.ismemberdescriptor(func):
        return True
    if inspect.ismethoddescriptor(func):
        return True
    module = inspect.getmodule(func)
    return module is builtins
