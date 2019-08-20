from dumbo.internal.stopwatch_context import StopwatchContext
from dataclasses import dataclass
from functools import wraps
from typing import List
from typing import Dict


def estimate_size(value):
    return 4


def estimate_throughput(value):
    return 2**30


def estimate_threshold(value):
    return estimate_size(value)/estimate_throughput(value)


Name = str

@dataclass
class RegisteredValue:
    name: Name


@dataclass
class CachedComputation:
    name: Name
    inputs: tuple
    computation_duration: float
    # outputs:


Cache = Dict[Name, Dict[tuple, CachedComputation]]

def create_cache() -> Cache:
    return {}


def find_computation(cache: Cache, name, inputs) -> CachedComputation:
    if name not in cache:
        return None
    return cache[name].get(inputs, None)


def dumbo():
    def wrapper(func):
        cache = {}

        @wraps(func)
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
