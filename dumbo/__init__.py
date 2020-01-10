from dumbo.internal import main

from dumbo.internal.main import init_dumbo

# TODO: what about exceptions?
# TODO: what about wrapping methods in class definitions?
# Shouldn't really support that maybe because we won't be able to perform
# code dependency checks for that...
dumbo = main.Dumbo.wrap_function


def _ensure_dumbo_init():
    if main.dumbo is None:
        print('Initializing Dumbo!')
        init_dumbo()


def _require_dumbo():
    if main.dumbo is None:
        raise RuntimeError("Dumbo not initialized!")


def register_external_value(unique_name, value):
    _ensure_dumbo_init()

    main.dumbo.register_external_value(unique_name, value)


def tag(tag_name, value):
    _ensure_dumbo_init()

    main.dumbo.tag(tag_name, value)


def get_tag_value(tag_name):
    _ensure_dumbo_init()

    return main.dumbo.get_tag_value(tag_name)


def get_external_value(unique_name):
    _ensure_dumbo_init()

    return main.dumbo.get_external_value(unique_name)


def flush_online_cache():
    _require_dumbo()
    main.dumbo.flush_cache()


def get_cached_value_identities(persisted=False):
    _ensure_dumbo_init()

    # TODO: add require_dumbo_init??? (so we don't accidentally initialize dumbo in a getter
    vids = main.dumbo.get_value_identities(persisted=persisted)

    # TODO: convert to dicts?
    return vids


def get_metadata(value):
    _require_dumbo()

    return main.dumbo.get_metadata(value)


def is_stale(value, *, depth=-1):
    _require_dumbo()

    return main.dumbo.is_stale(value, depth=depth)


def forget(value):
    _require_dumbo()

    main.dumbo.forget(value)


def run_cell(name, cell_code, namespace):
    _ensure_dumbo_init()

    main.dumbo.run_cell(name, cell_code, namespace)
