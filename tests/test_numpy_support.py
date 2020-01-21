import mamo
import mamo.support.numpy

import numpy as np

import tempfile

import pytest

add_np_execution_counter = 0


def add_np_code(a, b):
    global add_np_execution_counter
    add_np_execution_counter += 1
    return a + b


@pytest.mark.parametrize("size", [10, 1000])
def test_add_np(size):
    mamo.main.mamo = None

    a = np.random.normal(size=(size, size))
    b = np.random.normal(size=(size, size))
    c = np.random.normal(size=(size, size))

    add_np_execution_counter_old = add_np_execution_counter

    add_np = mamo.mamo(add_np_code)

    ab = add_np(a, b)
    ac = add_np(a, c)

    assert add_np(a, b) is ab
    assert add_np(a, c) is ac

    assert add_np_execution_counter - add_np_execution_counter_old == 2


@pytest.mark.parametrize("size", [10, 1000])
def test_add_np_persistent(size):
    with tempfile.TemporaryDirectory() as temp_storage_dir:
        mamo.main.mamo = None
        mamo.main.init_mamo(False, temp_storage_dir)

        add_np = mamo.mamo(add_np_code)

        a = np.random.normal(size=(size, size))
        b = np.random.normal(size=(size, size))
        c = np.random.normal(size=(size, size))

        add_np_execution_counter_old = add_np_execution_counter

        ab = add_np(a, b)
        ac = add_np(a, c)

        assert add_np(a, b) is ab
        assert add_np(a, c) is ac

        assert add_np_execution_counter - add_np_execution_counter_old == 2

        mamo.main.mamo.testing_close()

        mamo.main.mamo = None
        mamo.main.init_mamo(False, temp_storage_dir)

        add_np = mamo.mamo(add_np_code)

        add_np_execution_counter_old = add_np_execution_counter

        assert np.array_equal(add_np(a, b), ab)
        assert np.array_equal(add_np(a, c), ac)

        assert add_np_execution_counter - add_np_execution_counter_old == 0

        mamo.main.mamo.testing_close()
        mamo.main.mamo = None
