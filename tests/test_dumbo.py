from types import FunctionType
from typing import cast

import mamo
from mamo.internal import main

# Here, we just assume mamo as general memoization library.
from mamo.internal.identities import value_name_identity, ValueCallIdentity

from tests.testing import BoxedValue

# noinspection PyUnresolvedReferences
from tests.testing import mamo_fixture
from _pytest.fixtures import fixture

mamo_fib: FunctionType = None
get_global_var: FunctionType = None


def unwrapped_fib(n):
    if n < 0:
        return 0
    if n < 2:
        return 1
    return mamo_fib(n - 1) + mamo_fib(n - 2)


global_var = None


def unwrapped_get_global_var(offset):
    return global_var + offset


@fixture
def mamo_fib_fixture(mamo_fixture):
    global mamo_fib
    mamo_fib = mamo.mamo(unwrapped_fib)
    yield mamo_fib
    mamo_fib = None


@fixture
def mamo_get_global_var_fixture(mamo_fixture):
    global get_global_var
    get_global_var = mamo.mamo(unwrapped_get_global_var)
    yield mamo_fib
    get_global_var = None


def test_mamo_fib(mamo_fib_fixture):
    result = mamo_fib(8)
    assert result == 34
    assert len(mamo.get_cached_value_identities(False)) == 9
    assert len(mamo.get_cached_value_identities(False)) == 9

    assert len(mamo.get_cached_value_identities(False)) == 9
    del result
    mamo.flush_online_cache()
    assert len(mamo.get_cached_value_identities(False)) == 0
    assert len(mamo.get_cached_value_identities(True)) == 9


def test_mamo_fib_metadata(mamo_fib_fixture):
    i = 30
    mamo_fib(i)
    mamo.flush_online_cache()

    mamo_fib(i)
    mamo_fib(i)
    mamo_fib(i)
    mamo.flush_online_cache()

    result = mamo_fib(i)

    metadata = mamo.get_metadata(result)

    assert metadata.num_loads == 2
    assert metadata.num_cache_hits == 4
    assert metadata.call_duration > 0
    assert metadata.subcall_duration > 0
    assert metadata.total_load_durations > 0
    assert metadata.total_durations > metadata.call_duration
    assert metadata.call_duration > metadata.subcall_duration
    assert metadata.avg_load_duration > 0
    assert metadata.avg_overhead_duration > 0
    assert metadata.avg_total_duration > 0
    assert metadata.estimated_nomamo_call_duration > metadata.avg_total_duration
    assert metadata.estimated_saved_time > 0

    assert metadata == mamo_fib.get_metadata(i)


def test_mamo_func_api_works(mamo_fib_fixture):
    assert not mamo_fib.is_cached(8)
    assert mamo_fib.is_stale(8)

    result = mamo_fib(8)
    mamo.tag('test', result)
    del result

    assert mamo_fib.is_cached(8)
    assert not mamo_fib.is_stale(8)

    mamo.flush_online_cache()

    assert mamo_fib.get_tag_name(8) == 'test'

    assert not mamo.get_cached_value_identities(False)
    assert mamo_fib.is_cached(8)
    assert not mamo_fib.is_stale(8)

    mamo_fib.forget(8)

    assert not mamo_fib.is_cached(8)
    assert mamo_fib.is_stale(8)


def test_mamo_value_api_works(mamo_fib_fixture):
    result = mamo_fib(8)

    assert not mamo.is_stale(result)
    assert mamo.get_metadata(result)
    assert not mamo.get_tag_name(result)

    mamo.tag('test', result)

    assert mamo.get_tag_name(result) == 'test'
    assert mamo.get_tag_value('test') == result

    mamo.forget(result)

    assert mamo.is_stale(result)


def test_mamo_can_wrap_uninitialized():
    # and creates mamo on call

    assert main.mamo is None

    f = mamo.mamo(lambda: 1)

    assert f() == 1

    assert main.mamo is not None

    main.mamo.testing_close()
    main.mamo = None


def test_mamo_register_external_value(mamo_fib_fixture):
    magic_number = 15
    unique_name = "magic_number"

    mamo.register_external_value(unique_name, magic_number)

    assert mamo.get_external_value(unique_name) == magic_number

    result = mamo_fib_fixture(magic_number)

    assert cast(ValueCallIdentity, main.mamo.value_provider_mediator.identify_value(result)).args_vid[
               0] == value_name_identity(unique_name)

    mamo.register_external_value(unique_name, None)

    assert mamo.get_external_value(unique_name) is None


def test_mamo_tag(mamo_fib_fixture):
    result = mamo_fib(10)
    tag_name = "duck"

    assert mamo.get_tag_value(tag_name) is None

    mamo.tag(tag_name, result)

    assert mamo.get_tag_value(tag_name) is result

    mamo.tag(tag_name, None)

    assert mamo.get_tag_value(tag_name) is None


def test_run_cell(mamo_fixture):
    class Dummy:
        pass

    user_ns_obj = Dummy()
    user_ns_obj.var = None
    user_ns = user_ns_obj.__dict__

    user_ns_obj.boxed = BoxedValue("hello")
    cell_code = "global var; var = boxed"

    main.mamo.run_cell(None, cell_code, user_ns)

    assert user_ns_obj.var == user_ns_obj.boxed
    assert user_ns_obj.var is not user_ns_obj.boxed

    var_old = user_ns_obj.var

    main.mamo.run_cell(None, cell_code, user_ns)

    assert user_ns_obj.var is var_old


def test_run_named_cell(mamo_fixture):
    class Dummy:
        pass

    user_ns_obj = Dummy()
    user_ns_obj.var = None
    user_ns = user_ns_obj.__dict__

    user_ns_obj.boxed = BoxedValue("hello")
    cell_code = "global var; var = boxed"

    main.mamo.run_cell("named_cell", cell_code, user_ns)

    assert user_ns_obj.var == user_ns_obj.boxed
    assert user_ns_obj.var is not user_ns_obj.boxed

    var_old = user_ns_obj.var

    main.mamo.run_cell("named_cell", "pass", user_ns)

    assert user_ns_obj.var is var_old

# @mamo.mamo()
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
#     assert reflection.get_func_qualified_name(slow_operation) == "test_mamo.slow_operation"
