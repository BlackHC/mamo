import dumbo
import time
import dumbo.internal.stopwatch_context as swc


@dumbo.dumbo()
def slow_operation(a: int, b: int):
    time.sleep(a)
    return a + b


def test_slow_operation():
    with swc.StopwatchContext() as first_run:
        result = slow_operation(1, 3)
    assert result == 1 + 3

    with swc.StopwatchContext() as cached_run:
        result_cached = slow_operation(1, 3)

    assert result_cached == result
    assert cached_run.elapsed_time < first_run.elapsed_time


def test_get_func_qualified_name():
    assert dumbo.get_func_qualified_name(slow_operation) == "test_dumbo.slow_operation"
