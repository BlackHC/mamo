import dumbo
import time
import dumbo.internal.stopwatch_context as swc
import numpy as np
from dumbo.internal import reflection
from dumbo.internal import main


# Here, we just assume dumbo as general memoization library.


# Nice but breaks: "every call, different result", so we'll wrap it in numpy.
@dumbo.dumbo()
def fib(n):
    if n < 0:
        return 0
    if n < 2:
        return 1
    return fib(n-1)+fib(n-2)


def test_dumbo_fib():
    result = fib(8)
    assert result == 34
    assert len(main.dumbo.online_cache.value_to_vid) == 9
    assert len(main.dumbo.online_cache.vid_to_value) == 9


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
