from dataclasses import dataclass
import weakref


@dataclass
class DumboState:
    fid_cache: dict
    value_cache: weakref.WeakKeyDictionary

    def get_fid_entry(self, fid):
        if fid not in self.fid_cache:
            self.fid_cache[fid] = {}
        return self.fid_cache[fid]

    def add_value_cid(self, value, cid):
        if value not in self.value_cache:
            self.value_cache[value] = cid

        if self.value_cache[value] != cid:
            # TODO: better handling?
            print(f"{cid} has same result as {self.value_cache[value]}! Ignored!")

    def get_value_cid(self, value):
        return self.value_cache.get(value)


dumbo_state: DumboState = None


def init_dumbo():
    global dumbo_state
    assert dumbo_state is None
    dumbo_state = DumboState({}, weakref.WeakKeyDictionary())
