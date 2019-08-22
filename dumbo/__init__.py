from dumbo.internal.stopwatch_context import StopwatchContext
from functools import wraps
from dumbo.internal.call_identity import identify_call
from dumbo.internal.function_identity import identify_function
from dumbo.internal import state

# TODO: what about wrapping methods in class definitions?
# TODO: what about exceptions?
# Shouldn't really support that maybe because we won't be able to perform
# code dependency checks for that...
def dumbo():
    if not state.dumbo_state:
        state.init_dumbo()

    def wrapper(func):
        fid = identify_function(func)
        fid_entry = state.dumbo_state.get_fid_entry(fid)

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            cid = identify_call(fid, args, kwargs)
            if cid in fid_entry:
                return fid_entry[cid]

            result = func(*args, **kwargs)
            # TODO: we might want to keep multiple results for stochastic operations
            fid_entry[cid] = result
            state.dumbo_state.add_value_cid(result, cid)
            return result

        return wrapped_func
    return wrapper
