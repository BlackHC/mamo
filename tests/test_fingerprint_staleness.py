from mamo.internal import main
from mamo.internal import reflection

# noinspection PyUnresolvedReferences
from tests.testing import mamo_fixture


# TODO: this should be a unit test of a pure FingerprintRegistry!

global_func = None


def func_a():
    return 1


def func_b():
    return 1


def func_c():
    return global_func()


def func_d():
    return func_c()


def global_func1():
    return 1


def global_func2():
    return 2


# Let's make func_a/b/c all the same by name.
func_a.__qualname__ = func_b.__qualname__ = func_c.__qualname__ = "func"


def test_func_a_b_c_same():
    func_a_name = reflection.get_func_qualified_name(func_a)
    func_b_name = reflection.get_func_qualified_name(func_b)
    func_c_name = reflection.get_func_qualified_name(func_c)

    assert func_a_name == func_b_name
    assert func_b_name == func_c_name


def test_mamo_func_a_b_c_same(mamo_fixture):
    func_a_id = main.mamo.function_registry.identify_function(func_a)
    func_b_id = main.mamo.function_registry.identify_function(func_b)
    func_c_id = main.mamo.function_registry.identify_function(func_c)

    assert func_a_id == func_b_id
    assert func_b_id == func_c_id


def test_shallow_function_fingerprint(mamo_fixture):
    # Disable deep signatures.
    main.mamo.deep_fingerprint_source_prefix = None

    func_a_fingerprint = main.mamo.fingerprint_registry.fingerprint_function(func_a)
    func_b_fingerprint = main.mamo.fingerprint_registry.fingerprint_function(func_b)
    func_c_fingerprint = main.mamo.fingerprint_registry.fingerprint_function(func_c)

    assert func_a_fingerprint == func_b_fingerprint
    assert func_b_fingerprint != func_c_fingerprint


def test_deep_function_fingerprint_simple(mamo_fixture):
    # Enable deep signatures.
    main.mamo.deep_fingerprint_source_prefix = ""

    func_a_fingerprint = main.mamo.fingerprint_registry.fingerprint_function(func_a)
    func_b_fingerprint = main.mamo.fingerprint_registry.fingerprint_function(func_b)
    func_c_fingerprint = main.mamo.fingerprint_registry.fingerprint_function(func_c)

    assert func_a_fingerprint == func_b_fingerprint
    assert func_b_fingerprint != func_c_fingerprint


def test_deep_function_fingerprint_global_calls(mamo_fixture):
    # Enable deep signatures.
    main.mamo.deep_fingerprint_source_prefix = ""

    global global_func
    global_func = global_func1

    func_c_fingerprint_1 = main.mamo.fingerprint_registry.fingerprint_function(func_c)
    func_d_fingerprint_1 = main.mamo.fingerprint_registry.fingerprint_function(func_d)

    global_func = global_func2

    func_c_fingerprint_2 = main.mamo.fingerprint_registry.fingerprint_function(func_c)
    func_d_fingerprint_2 = main.mamo.fingerprint_registry.fingerprint_function(func_d)

    assert func_c_fingerprint_1 != func_c_fingerprint_2
    assert func_d_fingerprint_1 != func_d_fingerprint_2
