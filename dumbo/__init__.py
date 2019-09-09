from dumbo.internal import main
from dumbo.internal.main import init_dumbo

# TODO: what about exceptions?
# TODO: what about wrapping methods in class definitions?
# Shouldn't really support that maybe because we won't be able to perform
# code dependency checks for that...
dumbo = main.Dumbo.wrap_function


def _ensure_dumbo_init():
    if main.dumbo is None:
        main.init_dumbo()


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
