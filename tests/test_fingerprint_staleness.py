from dumbo.internal import main
from dumbo.internal import reflection
# noinspection PyUnresolvedReferences
from .testing import dumbo_fixture


global_var = 1
global_func = None


def func_a():
    return global_var


def func_b():
    return global_var


def func_c():
    return global_func()


def global_func1():
    return 1


def global_func2():
    return 2


# Let's make func_a/b/c all the same by name.
func_a.__qualname__ = func_b.__qualname__ = func_c.__qualname__ = 'func'


def test_func_a_b_c_same():
    func_a_name = reflection.get_func_qualified_name(func_a)
    func_b_name = reflection.get_func_qualified_name(func_b)
    func_c_name = reflection.get_func_qualified_name(func_c)

    assert func_a_name == func_b_name
    assert func_b_name == func_c_name


def test_dumbo_func_a_b_c_same(dumbo_fixture):
    func_a_id = main.dumbo._identify_function(func_a)
    func_b_id = main.dumbo._identify_function(func_b)
    func_c_id = main.dumbo._identify_function(func_c)

    assert func_a_id == func_b_id
    assert func_b_id == func_c_id


def test_shallow_function_fingerprint(dumbo_fixture):
    # Disable deep signatures.
    main.dumbo.deep_fingerprint_source_prefix = None

    func_a_fingerprint = main.dumbo._get_function_fingerprint(func_a)
    func_b_fingerprint = main.dumbo._get_function_fingerprint(func_b)
    func_c_fingerprint = main.dumbo._get_function_fingerprint(func_c)

    assert func_a_fingerprint == func_b_fingerprint
    assert func_b_fingerprint != func_c_fingerprint


def test_deep_function_fingerprint_simple(dumbo_fixture):
    # Enable deep signatures.
    main.dumbo.deep_fingerprint_source_prefix = ""

    func_a_fingerprint = main.dumbo._get_function_fingerprint(func_a)
    func_b_fingerprint = main.dumbo._get_function_fingerprint(func_b)
    func_c_fingerprint = main.dumbo._get_function_fingerprint(func_c)

    assert func_a_fingerprint == func_b_fingerprint
    assert func_b_fingerprint != func_c_fingerprint


def test_deep_function_fingerprint_global_loads(dumbo_fixture):
    # Enable deep signatures.
    main.dumbo.deep_fingerprint_source_prefix = ""

    global global_var
    global_var = 1

    func_b_fingerprint_1 = main.dumbo._get_function_fingerprint(func_b)

    global_var = 2

    func_b_fingerprint_2 = main.dumbo._get_function_fingerprint(func_b)

    assert func_b_fingerprint_1 != func_b_fingerprint_2


def test_deep_function_fingerprint_global_calls(dumbo_fixture):
    # Enable deep signatures.
    main.dumbo.deep_fingerprint_source_prefix = ""

    global global_func
    global_func = global_func1

    func_c_fingerprint_1 = main.dumbo._get_function_fingerprint(func_c)

    global_func = global_func2

    func_c_fingerprint_2 = main.dumbo._get_function_fingerprint(func_c)

    assert func_c_fingerprint_1 != func_c_fingerprint_2


def test_deep_function_fingerprint_global_calls_deep(dumbo_fixture):
    # Enable deep signatures.
    main.dumbo.deep_fingerprint_source_prefix = ""

    global global_func, global_var
    global_func = func_a
    global_var = 1

    func_c_fingerprint_1 = main.dumbo._get_function_fingerprint(func_c)

    global_var = 2

    func_c_fingerprint_2 = main.dumbo._get_function_fingerprint(func_c)

    assert func_c_fingerprint_1 != func_c_fingerprint_2

