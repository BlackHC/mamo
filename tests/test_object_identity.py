import dumbo.internal.function_identity as object_identity


def a_dummy_func():
    pass


def test_get_func_qualified_name_local_function():
    assert object_identity.get_func_qualified_name(a_dummy_func) == "test_object_identity.a_dummy_func"


def test_get_func_qualified_name_nested_function():
    def nested_func():
        pass

    assert object_identity.get_func_qualified_name(nested_func) == "test_object_identity.test_get_func_qualified_name_nested_function.<locals>.nested_func"


def test_get_func_qualified_name_imported_function():
    assert object_identity.get_func_qualified_name(object_identity.get_func_qualified_name) == "dumbo.internal.object_identity.get_func_qualified_name"
