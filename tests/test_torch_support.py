import dumbo
import dumbo.support.torch

import torch as th

import tempfile

import pytest

add_th_execution_counter = 0


def add_th_code(a, b):
    global add_th_execution_counter
    add_th_execution_counter += 1
    return a + b


@pytest.mark.parametrize("size", [10, 1000])
def test_add_th(size):
    dumbo.main.dumbo = None

    a = th.rand(size=(size, size))
    b = th.rand(size=(size, size))
    c = th.rand(size=(size, size))

    add_th_execution_counter_old = add_th_execution_counter

    add_th = dumbo.dumbo()(add_th_code)

    ab = add_th(a, b)
    ac = add_th(a, c)

    assert add_th(a, b) is ab
    assert add_th(a, c) is ac

    assert add_th_execution_counter - add_th_execution_counter_old == 2


@pytest.mark.parametrize("size", [10, 1000])
def test_add_th_persistent(size):
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        dumbo.main.dumbo = None
        dumbo.main.init_dumbo(False, temp_storage_dir)

        add_th = dumbo.dumbo()(add_th_code)

        a = th.rand(size=(size, size))
        b = th.rand(size=(size, size))
        c = th.rand(size=(size, size))

        add_th_execution_counter_old = add_th_execution_counter

        ab = add_th(a, b)
        ac = add_th(a, c)

        assert add_th(a, b) is ab
        assert add_th(a, c) is ac

        assert add_th_execution_counter - add_th_execution_counter_old == 2

        dumbo.main.dumbo.close()

        dumbo.main.dumbo = None
        dumbo.main.init_dumbo(False, temp_storage_dir)

        add_th = dumbo.dumbo()(add_th_code)

        add_th_execution_counter_old = add_th_execution_counter

        assert th.allclose(add_th(a, b), ab)
        assert th.allclose(add_th(a, c), ac)

        assert add_th_execution_counter - add_th_execution_counter_old == 0

        dumbo.main.dumbo.close()
        dumbo.main.dumbo = None