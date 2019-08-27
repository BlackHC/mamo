from typing import Callable

from dumbo.internal.reflection import ModuleRegistry
from objproxies import ObjectProxy

RETURN_HANDLER_REGISTRY: ModuleRegistry[Callable] = ModuleRegistry()


def wrap_return_value(value):
    # We cannot really do anything about None sadly.
    # Why?
    # Because we usually test for None using 'is\is not None'
    # and having a proxy breaks that.
    # The general rule is that one should not dumbo 'None' results

    # TODO: raise or log?
    if value is None:
        return None

    # Treat tuples different for functions returning multiple values.
    # We usually want to wrap them separately.
    if isinstance(value, tuple):
        return tuple(wrap_return_value(item) for item in value)

    # Otherwise, wrap the value using an available return handler or using a generic proxy.
    # If return_handler returns None, we use the default behavior.
    # TODO: log etc
    return_handler = RETURN_HANDLER_REGISTRY.get(value)
    wrapped_value = None

    if return_handler is not None:
        wrapped_value = return_handler(value)

    if wrapped_value is None:
        # What do we do?
        # We just use a generic proxy class.
        wrapped_value = ObjectProxy(value)

    return wrapped_value
