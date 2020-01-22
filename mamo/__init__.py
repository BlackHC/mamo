from mamo.internal import main

from mamo.internal.main import init_mamo

# TODO: what about exceptions?
# TODO: what about wrapping methods in class definitions?
# Shouldn't really support that maybe because we won't be able to perform
# code dependency checks for that...
mamo = main.Mamo.wrap_function


def _ensure_mamo_init():
    if main.mamo is None:
        print('Initializing Mamo!')
        init_mamo()


def _require_mamo():
    if main.mamo is None:
        raise RuntimeError("Mamo not initialized!")


def register_external_value(unique_name, value):
    _ensure_mamo_init()

    main.mamo.register_external_value(unique_name, value)


def tag(tag_name, value):
    _ensure_mamo_init()

    main.mamo.tag(tag_name, value)


def get_tag_value(tag_name):
    _ensure_mamo_init()

    return main.mamo.get_tag_value(tag_name)


def get_tag_name(value):
    _require_mamo()

    return main.mamo.get_tag_name(value)


def get_external_value(unique_name):
    _ensure_mamo_init()

    return main.mamo.get_external_value(unique_name)


def flush_online_cache():
    _require_mamo()
    main.mamo.flush_cache()


def flush_value(value):
    _require_mamo()
    main.mamo.flush_value(value)


def get_cached_value_identities(persisted=False):
    _ensure_mamo_init()

    # TODO: add require_mamo_init??? (so we don't accidentally initialize mamo in a getter
    vids = main.mamo.get_value_identities(persisted=persisted)

    # TODO: convert to dicts?
    return vids


def get_metadata(value):
    _require_mamo()

    return main.mamo.get_metadata(value)


def is_stale(value, *, depth=-1):
    _require_mamo()

    return main.mamo.is_stale(value, depth=depth)


def forget(value):
    _require_mamo()

    main.mamo.forget(value)


def run_cell(name, cell_code, namespace):
    _ensure_mamo_init()

    main.mamo.run_cell(name, cell_code, namespace)
