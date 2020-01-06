import dis
import hashlib
import inspect
import marshal
from dataclasses import dataclass
from types import FunctionType, CodeType
import builtins

# Bytecode-extracted features. Independent of runtime and can be cached.
from typing import FrozenSet, Tuple, Optional


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


# TODO: extract a helper class that knows how to walk the instruction list
def get_calls(func_or_code: FunctionType):
    def unroll_call(leftover_stacksize):
        nonlocal instruction, j
        # + 1 as we ignore the return value that will be pushed onto the stack.
        stack_size = 1 - dis.stack_effect(instruction.opcode, instruction.arg)

        while j >= 0 and stack_size > leftover_stacksize:
            instruction = instructions[j]
            stack_size -= dis.stack_effect(instruction.opcode, instruction.arg)
            j -= 1

    def collect_callee():
        nonlocal instruction, j

        while j >= 0:
            instruction = instructions[j]
            if instruction.opname == "LOAD_GLOBAL":
                reversed_qualified_name.append(instruction.argval)
                called_funcs.add(tuple(reversed(reversed_qualified_name)))
                break
            elif instruction.opname in ("LOAD_ATTR",):
                reversed_qualified_name.append(instruction.argval)
            else:
                break
            j -= 1

    called_funcs = set()

    instructions = list(dis.get_instructions(func_or_code))
    for i in range(len(instructions)):

        instruction = instructions[i]
        if instruction.opname in ("CALL_FUNCTION", "CALL_FUNCTION_KW", "CALL_FUNCTION_EX"):
            # We go back in reverse now and pick up LOAD_ATTRs and LOAD_GLOBAL.
            reversed_qualified_name = []
            j = i - 1

            unroll_call(1)

            collect_callee()
        elif instruction.opname == 'CALL_METHOD':
            # We go back in reverse now and pick up LOAD_ATTRs and LOAD_GLOBAL.
            reversed_qualified_name = []
            j = i - 1

            unroll_call(2)

            instruction = instructions[j]
            if instruction.opname == 'LOAD_METHOD':
                reversed_qualified_name.append(instruction.argval)
                j -= 1
                collect_callee()

    return called_funcs


def get_global_loads_stores(func_or_code):
    loads = set()
    global_stores = set()

    instructions = list(reversed(list(dis.get_instructions(func_or_code))))
    while instructions:
        instruction = instructions.pop()
        if instruction.opname == "STORE_GLOBAL":
            global_stores.add(instruction.argval)
        elif instruction.opname == "LOAD_GLOBAL":
            qualified_name = [instruction.argval]

            # Now try to resolve attribute accesses.
            while instructions:
                next_instruction = instructions[-1]
                if next_instruction.opname in ("LOAD_ATTR", "LOAD_METHOD"):
                    instructions.pop()
                    qualified_name.append(next_instruction.argval)
                else:
                    break

            loads.add(tuple(qualified_name))

    return loads, global_stores


def get_code_object_fingerprint(code_object: CodeType):
    # TODO: add cache?
    hash_method = hashlib.md5(code_object.co_code)
    hash_method.update(marshal.dumps(code_object.co_consts))
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

    loads, stores = get_global_loads_stores(func)
    calls = get_calls(func)

    loads.difference_update(calls)

    loads = {load for load in loads if load[0] not in stores}
    calls = {call for call in calls if call[0] not in stores}

    return FunctionDependencies(frozenset(loads), frozenset(stores), frozenset(calls))


def is_func_local(func, local_prefix: Optional[str]):
    module = inspect.getmodule(func)

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
    module = inspect.getmodule(func)
    return module is builtins
