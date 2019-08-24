import hashlib


def get_qualified_name(func):
    # TODO: handle Jupyter notebooks?
    # In notebooks, __module__ will be "__main__".
    return f"{func.__module__}.{func.__qualname__}"


def get_type_qualified_name(value):
    return get_qualified_name(type(value))


def get_func_qualified_name(func):
    return get_qualified_name(func)


def get_func_hash(func):
    return hashlib.md5(func.__code__.co_code).hexdigest()


def get_value_hash(value):
    # TODO: support more types... seriously
    if isinstance(value, (int, float, str,)):
        return hash(value)
    return hashlib.md5(value).hexdigest()
