import dis
import inspect
import dis as d2


class A:
    class B:
        @staticmethod
        def c():
            pass


def call_nested_static_method():
    A.B.c()


def call_nested_module_method():
    d2.sys.exc_info()


def test_call_nested_module_method():
    dis.dis(call_nested_module_method)


def test_dis_call_nested_static_method():
    dis.dis(call_nested_static_method)


def local_func():
    return "hello"


def local_func2():
    return "hello:"


def dis_local_func():
    dis.get_instructions(local_func)


def call_local_func():
    local_func()


def test_dis_dis_local_func():
    dis.dis(dis_local_func)


def test_dis_call_local_func():
    dis.dis(call_local_func)


def test_dis_load_global():
    for instr in dis.Bytecode(call_local_func):
        print(instr.opname, instr.argval, type(instr.argval))


def is_function_local(func, local_prefix):
    module = inspect.getmodule(func)
    # Python's builtin module does not have a __file__ field.
    if not hasattr(module, '__file__'):
        return False

    return module.__file__.startswith(local_prefix)


def test_function_module():
    module = inspect.getmodule(local_func)
    print(module)
    print(module.__file__)

    print(inspect.getmodule(dis.get_instructions).__file__)


def test_is_function_local():
    local_prefix = r"C:\Users\black\Documents\dumbo"
    assert not is_function_local(print, local_prefix)
    assert is_function_local(local_func, local_prefix)
    assert not is_function_local(dis.disassemble, local_prefix)


def test_hash_code_objects():
    # Need to compare the bytecode instructions themselves.
    # An issue is that line numbers are part of the bytecode, so any line changes before a function
    # will affect the hash!
    assert not hash(dis.Bytecode(local_func)) == hash(dis.Bytecode(local_func))
    assert hash(tuple(dis.Bytecode(local_func))) == hash(tuple(dis.Bytecode(local_func)))

    # Let's import the same module twice.
    assert hash(dis.get_instructions.__code__.co_code) == hash(d2.get_instructions.__code__.co_code)

    # This is quite cool!
    # Don't have to use dis and can just use co_code directly
    # It doesn't seem dependent on line numbers!
    assert hash(local_func.__code__.co_code) == hash(local_func2.__code__.co_code)
    # print(hash(local_func.__code__.co_code))


def test_co_code():
    print(type(local_func.__code__.co_code))


def extract_call_names(func):
    # TODOs: support CALL_METHOD and others
    called_funcs = []

    instructions = list(dis.get_instructions(func))
    for i in range(len(instructions)):
        instruction = instructions[i]
        if instruction.opname == 'CALL_FUNCTION':
            stack_size = 1-dis.stack_effect(instruction.opcode, instruction.arg)
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
                elif instruction.opname == 'LOAD_ATTR':
                    reversed_qualified_name.append(instruction.argval)
                else:
                    break
                j -= 1

    return called_funcs


def local_func_arg2(a,b):
    return a + b


def call_local_func_arg2():
    a = 2
    b = 4
    local_func2(a*b, a+b)


def test_spike_read_module_name():
    assert extract_call_names(call_local_func) == [('local_func',)]
    assert extract_call_names(call_local_func_arg2) == [('local_func2',)]