from dumbo.internal import reflection


def a_dummy_func():
    pass


def test_get_func_qualified_name_local_function():
    assert reflection.get_func_qualified_name(a_dummy_func) == "tests.test_object_identity.a_dummy_func"


def test_get_func_qualified_name_nested_function():
    def nested_func():
        pass

    assert reflection.get_func_qualified_name(nested_func) == "tests.test_object_identity.test_get_func_qualified_name_nested_function.<locals>.nested_func"


def test_get_func_qualified_name_imported_function():
    assert reflection.get_func_qualified_name(reflection.get_func_qualified_name) == "dumbo.internal.reflection.get_func_qualified_name"
