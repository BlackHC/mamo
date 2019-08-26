from dumbo.internal.stopwatch_context import StopwatchContext
from functools import wraps
from dumbo.internal import main

# TODO: what about wrapping methods in class definitions?
# TODO: what about exceptions?
# Shouldn't really support that maybe because we won't be able to perform
# code dependency checks for that...
def dumbo():
    if not main.dumbo:
        main.init_dumbo()

    return main.dumbo.wrap_function
