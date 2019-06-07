from dumbo.internal.stopwatch_context import StopwatchContext
from dataclasses import dataclass


def estimate_size(value):
    return 4


def estimate_throughput(value):
    return 2**30


def estimate_threshold(value):
    return estimate_size(value)/estimate_throughput(value)


def dumbo():
    def wrapper(func):
        cache = {}

        def wrapped_func(*args, **kwargs):
            # Check whether the result has already been cached?
            key = (args, tuple(kwargs.items()))
            if key in cache:
                return cache[key]
            with StopwatchContext() as stopwatch_context:
                result = func(*args, **kwargs)
            # Decide whether to cache the result.
            if stopwatch_context.elapsed_time > 0.1:
                cache[key] = result
            return result
        return wrapped_func
    return wrapper
