import dis
import hashlib
import marshal
from types import FunctionType
from dataclasses import dataclass


def get_module_name(value):
    return value.__class__.__module__


def get_qualified_name(func):
    # TODO: handle Jupyter notebooks?
    # In notebooks, __module__ will be "__main__".
    return f"{func.__module__}.{func.__qualname__}"


def get_type_qualified_name(value):
    return get_qualified_name(type(value))


def get_func_qualified_name(func):
    return get_qualified_name(func)


def get_func_calls(func: FunctionType):
    # TODOs: support CALL_METHOD and LOAD_METHOD?
    called_funcs = set()

    instructions = list(dis.get_instructions(func))
    for i in range(len(instructions)):
        instruction = instructions[i]
        if instruction.opname == 'CALL_FUNCTION':
            # + 1 as we ignore the return value that will be pushed onto the stack.
            stack_size = 1 - dis.stack_effect(instruction.opcode, instruction.arg)
            # We go back in reverse now and pick up LOAD_ATTRs and LOAD_GLOBAL.
            reversed_qualified_name = []
            j = i - 1

            while j >= 0 and stack_size > 1:
                instruction = instructions[j]
                stack_size -= dis.stack_effect(instruction.opcode, instruction.arg)
                j -= 1

            while j >= 0:
                instruction = instructions[j]
                if instruction.opname == 'LOAD_GLOBAL':
                    reversed_qualified_name.append(instruction.argval)
                    called_funcs.append(tuple(reversed(reversed_qualified_name)))
                    break
                elif instruction.opname in ('LOAD_ATTR',):
                    reversed_qualified_name.append(instruction.argval)
                else:
                    break
                j -= 1

    return called_funcs


def get_func_global_loads(func):
    loads = set()

    instructions = list(reversed(list(dis.get_instructions(func))))
    while instructions:
        instruction = instructions.pop()
        if instruction.opname == 'LOAD_GLOBAL':
            qualified_name = [instruction.argval]

            # Now try to resolve attribute accesses.
            while instructions:
                next_instruction = instructions[-1]
                if next_instruction.opname in ('LOAD_ATTR', 'LOAD_METHOD'):
                    instructions.pop()
                    qualified_name.append(next_instruction.argval)
                else:
                    break

            loads.add(tuple(qualified_name))

    return loads


def get_func_hash(func: FunctionType):
    # TODO: neeod to hash/include co_consts, too
    hasher = hashlib.md5(func.__code__.co_code)
    hasher.update(marshal.dumps(func.__code__.co_consts))
    return hasher.digest()


def resolve_qualified_name(qualified_name):
    resolved = globals().get(qualified_name[0])
    for attr in qualified_name[1:]:
        if resolved is None:
            break
        resolved = getattr(resolved, attr)
    return resolved


def resolve_qualified_names(qualified_names: set):
    resolved_dict = {}
    for qualified_name in qualified_names:
        resolved_dict[qualified_name] = resolve_qualified_name(qualified_name)
    return resolved_dict


def get_runtime_func_fingerprint(func: FunctionType):
    # We can cache the globals dependencies and the code hash.
    # Then we need to create fingerprints for all referenced global values
    # And figure out whether we want to include dependencies for functions that are being
    # called.

    # TODO: cache these three
    func_hash = get_func_hash(func)
    loads = get_func_global_loads(func)
    calls = get_func_calls(func)

    loads.difference_update(calls)

    # Resolve globals and calls.
    # Get signatures for globals
    # Get runtime signatures for calls.
