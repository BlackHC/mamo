from dumbo.internal.stopwatch_context import StopwatchContext
from dataclasses import dataclass


def dumbo():
    def wrapper(func):
        cache = {}

        def wrapped_func(*args, **kwargs):
            # Check whether the result has already been cached?
            key = (args, list(kwargs.items()))
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
