from mamo.internal import reflection
from mamo.internal.reflection import FunctionDependencies

global_variable = None


def a_dummy_func():
    pass


def simple_func(a):
    return a


def calls_simple_func():
    simple_func(1)


def calls_kw_func():
    simple_func(a=1)


def calls_ex_func(**kwargs):
    simple_func(**kwargs)


def calls_nested_module():
    reflection.dis.get_instructions(None)


def calls_changed_global():
    global global_variable
    global_variable = reflection.dis
    global_variable.get_instructions(None)


def reads_writes_global():
    global global_variable
    global_variable = reflection.dis
    return global_variable.get_instructions


def test_get_func_qualified_name_local_function():
    assert reflection.get_func_qualified_name(a_dummy_func) == "tests.test_reflection.a_dummy_func"


def test_get_func_qualified_name_nested_function():
    def nested_func():
        pass

    assert (
            reflection.get_func_qualified_name(nested_func)
            == "tests.test_reflection.test_get_func_qualified_name_nested_function.<locals>.nested_func"
    )


def test_get_func_qualified_name_imported_function():
    assert (
            reflection.get_func_qualified_name(reflection.get_func_qualified_name)
            == "mamo.internal.reflection.get_func_qualified_name"
    )


def test_get_module_name_primitive_value():
    assert reflection.get_module_name(1) == "builtins"


def test_get_module_name_custom_class():
    class DummyClass:
        pass

    assert reflection.get_module_name(DummyClass()) == "tests.test_reflection"


def test_get_func_deps_simple():
    assert reflection.get_func_deps(calls_simple_func) == FunctionDependencies(global_loads=frozenset(),
                                                                               global_stores=frozenset(),
                                                                               func_calls=frozenset({('simple_func',)}))


def test_get_func_deps_kw():
    assert reflection.get_func_deps(calls_kw_func) == FunctionDependencies(global_loads=frozenset(),
                                                                           global_stores=frozenset(),
                                                                           func_calls=frozenset({('simple_func',)}))


def test_get_func_deps_ex():
    assert reflection.get_func_deps(calls_ex_func) == FunctionDependencies(global_loads=frozenset(),
                                                                           global_stores=frozenset(),
                                                                           func_calls=frozenset({('simple_func',)}))


def test_get_func_deps_nested_module():
    assert reflection.get_func_deps(calls_nested_module) == FunctionDependencies(global_loads=frozenset(),
                                                                                 global_stores=frozenset(),
                                                                                 func_calls=frozenset({('reflection',
                                                                                                        'dis',
                                                                                                        'get_instructions')}))


def test_get_func_deps_ignores_calls_from_changed():
    deps = reflection.get_func_deps(calls_changed_global)
    assert deps == FunctionDependencies(global_loads=frozenset({('reflection', 'dis')}),
                                        global_stores=frozenset({'global_variable'}), func_calls=frozenset())


def test_get_func_deps_ignores_calls_from_changed_globals():
    deps = reflection.get_func_deps(reads_writes_global)
    # Removes loads of globals that are also stored. (Conservative)
    assert deps == FunctionDependencies(global_loads=frozenset({('reflection', 'dis')}),
                                        global_stores=frozenset({'global_variable'}), func_calls=frozenset())


def test_isbuiltin():
    assert reflection.is_func_builtin(print)
    assert reflection.is_func_builtin(str)
    assert reflection.is_func_builtin("a".capitalize)
    assert reflection.is_func_builtin(str.capitalize)
    assert reflection.is_func_builtin(object.__init__)
    assert reflection.is_func_builtin(type(int))

    class LocalClass:
        @staticmethod
        def staticmethod():
            pass

    def local_func():
        pass

    assert reflection.is_func_builtin(LocalClass.__init__)

    assert not reflection.is_func_builtin(local_func)
    assert not reflection.is_func_builtin(LocalClass.staticmethod)
