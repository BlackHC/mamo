import inspect
import types


class A:
    @classmethod
    def class_method(cls, arg):
        return arg

    @staticmethod
    def static_method(arg):
        return arg

    def method(self, arg):
        return arg


def global_function(arg):
    return arg


def test_types_match():
    assert inspect.isfunction(global_function)
    assert not inspect.isfunction(A().method)

    assert inspect.ismethod(A().method)
    assert not inspect.isfunction(A().method)

    assert not inspect.ismethod(A().static_method)
    assert inspect.isfunction(A().static_method)

    assert inspect.ismethod(A().class_method)
    assert not inspect.isfunction(A().class_method)

    assert inspect.isclass(A)

    assert isinstance(A.__init__, types.WrapperDescriptorType)

    assert inspect.isbuiltin(print)
    assert inspect.ismethoddescriptor(str.capitalize)
    assert not inspect.ismethod(str.capitalize)
    assert inspect.isbuiltin("A".capitalize)


def test_get_func():
    assert inspect.isfunction(A().method.__func__)
    assert inspect.isfunction(A().class_method.__func__)
    assert inspect.isfunction(A().static_method)


def test_qualname():
    assert str.__qualname__
    assert str.capitalize.__qualname__
    assert "a".capitalize.__qualname__




