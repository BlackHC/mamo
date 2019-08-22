from dumbo.internal.stopwatch_context import StopwatchContext
from functools import wraps
from dumbo.internal import state

# TODO: what about wrapping methods in class definitions?
# TODO: what about exceptions?
# Shouldn't really support that maybe because we won't be able to perform
# code dependency checks for that...
def dumbo():
    if not state.dumbo:
        state.init_dumbo()

    return state.dumbo.wrap_function
