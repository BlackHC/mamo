from dumbo.internal.common.id_set import IdSet
from tests.collection_testing.test_mutable_set import MutableSetTests


class TestIdSet(MutableSetTests):
    mutable_set = IdSet

    @staticmethod
    def get_element(i):
        return [i]
