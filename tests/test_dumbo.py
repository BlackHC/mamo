from types import FunctionType

import dumbo
from dumbo.internal import main

# Here, we just assume dumbo as general memoization library.
from dumbo.internal.identities import ValueNameIdentity

from tests.testing import BoxedValue
# noinspection PyUnresolvedReferences
from tests.testing import dumbo_fixture
from _pytest.fixtures import fixture


dumbo_fib: FunctionType = None
get_global_var: FunctionType = None


def unwrapped_fib(n):
    if n < 0:
        return 0
    if n < 2:
        return 1
    return dumbo_fib(n - 1) + dumbo_fib(n - 2)


global_var = None


def unwrapped_get_global_var(offset):
    return global_var + offset


@fixture
def dumbo_fib_fixture(dumbo_fixture):
    global dumbo_fib
    dumbo_fib = dumbo.dumbo(unwrapped_fib)
    yield dumbo_fib
    dumbo_fib = None


@fixture
def dumbo_get_global_var_fixture(dumbo_fixture):
    global get_global_var
    get_global_var = dumbo.dumbo(unwrapped_get_global_var)
    yield dumbo_fib
    get_global_var = None


def test_dumbo_fib(dumbo_fib_fixture):
    result = dumbo_fib(8)
    assert result == 34
    assert len(main.dumbo.online_cache.value_id_to_vid) == 9
    assert len(main.dumbo.online_cache.vid_to_value) == 9

    assert len(dumbo.get_cached_value_identities(False)) == 9
    dumbo.flush_online_cache()
    assert len(dumbo.get_cached_value_identities(False)) == 0
    assert len(dumbo.get_cached_value_identities(True)) == 9


def test_dumbo_can_wrap_uninitialized():
    # and creates dumbo on call

    assert main.dumbo is None

    f = dumbo.dumbo(lambda: 1)

    assert f() == 1

    assert main.dumbo is not None

    main.dumbo.testing_close()
    main.dumbo = None


def test_dumbo_register_external_value(dumbo_fib_fixture):
    magic_number = 15
    unique_name = "magic_number"

    dumbo.register_external_value(unique_name, magic_number)

    assert dumbo.get_external_value(unique_name) == magic_number

    result = dumbo_fib_fixture(magic_number)

    assert main.dumbo.online_cache.value_id_to_vid[id(result)].cid.args_vid[0] == ValueNameIdentity(unique_name)

    dumbo.register_external_value(unique_name, None)

    assert dumbo.get_external_value(unique_name) is None


def test_is_cached_is_stale_deep_works(dumbo_get_global_var_fixture):
    # Enable deep signatures.
    main.dumbo.deep_fingerprint_source_prefix = ""

    global global_var
    global_var = 1

    assert not get_global_var.is_cached(5)
    assert get_global_var.is_stale(5)

    assert get_global_var(5) == 6
    assert get_global_var.is_cached(5)
    assert not get_global_var.is_stale(5)

    global_var = 2

    assert get_global_var.is_cached(5)
    assert get_global_var.is_stale(5)

    get_global_var.forget(5)
    assert get_global_var(5) == 7

    assert get_global_var.is_cached(5)
    assert not get_global_var.is_stale(5)


def test_is_cached_is_stale_arg_change(dumbo_get_global_var_fixture):
    # Enable deep signatures.
    main.dumbo.deep_fingerprint_source_prefix = ""

    global global_var

    @dumbo.dumbo
    def outer(b):
        return b + 1

    global_var = 1

    assert not get_global_var.is_cached(1)
    assert get_global_var.is_stale(1)

    result = get_global_var(1)

    assert not get_global_var.is_stale(1)
    assert not dumbo.is_stale(result)

    outer_result = outer(result)

    global_var = 2

    assert dumbo.is_stale(result)
    assert dumbo.is_stale(outer_result, depth=-1)

    # TODO: allow for automatic recomputation!
    dumbo.forget(result)
    result_new = get_global_var(1)

    assert dumbo.is_stale(result)
    assert not dumbo.is_stale(result_new)
    assert dumbo.is_stale(outer_result)

    dumbo.forget(outer_result)
    outer_result_new = outer(result_new)

    assert not dumbo.is_stale(outer_result_new)



def test_dumbo_tag(dumbo_fib_fixture):
    result = dumbo_fib(10)
    tag_name = "duck"

    assert dumbo.get_tag_value(tag_name) is None

    dumbo.tag(tag_name, result)

    assert dumbo.get_tag_value(tag_name) is result

    dumbo.tag(tag_name, None)

    assert dumbo.get_tag_value(tag_name) is None


def test_run_cell(dumbo_fixture):
    class Dummy:
        pass

    user_ns_obj = Dummy()
    user_ns_obj.var = None
    user_ns = user_ns_obj.__dict__

    user_ns_obj.boxed = BoxedValue("hello")
    cell_code = "global var; var = boxed"

    main.dumbo.run_cell(None, cell_code, user_ns)

    assert user_ns_obj.var == user_ns_obj.boxed
    assert user_ns_obj.var is not user_ns_obj.boxed

    var_old = user_ns_obj.var

    main.dumbo.run_cell(None, cell_code, user_ns)

    assert user_ns_obj.var is var_old


def test_run_named_cell(dumbo_fixture):
    class Dummy:
        pass

    user_ns_obj = Dummy()
    user_ns_obj.var = None
    user_ns = user_ns_obj.__dict__

    user_ns_obj.boxed = BoxedValue("hello")
    cell_code = "global var; var = boxed"

    main.dumbo.run_cell("named_cell", cell_code, user_ns)

    assert user_ns_obj.var == user_ns_obj.boxed
    assert user_ns_obj.var is not user_ns_obj.boxed

    var_old = user_ns_obj.var

    main.dumbo.run_cell("named_cell", "pass", user_ns)

    assert user_ns_obj.var is var_old



# @dumbo.dumbo()
# def slow_operation(a: int, b: int):
#     time.sleep(a)
#     return a + b


# def test_slow_operation():
#     with swc.StopwatchContext() as first_run:
#         result = slow_operation(1, 3)
#     assert result == 1 + 3
#
#     with swc.StopwatchContext() as cached_run:
#         result_cached = slow_operation(1, 3)
#
#     assert result_cached == result
#     assert cached_run.elapsed_time < first_run.elapsed_time

#
# def test_get_func_qualified_name():
#     assert reflection.get_func_qualified_name(slow_operation) == "test_dumbo.slow_operation"
