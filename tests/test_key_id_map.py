from dumbo.internal.common.key_id_dict import KeyIdDict
from tests.collection_testing.test_mutable_mapping import MutableMappingTests


class TestKeyIdDict(MutableMappingTests):
    mutable_mapping = KeyIdDict

    @staticmethod
    def get_key(i):
        return [i]
