from mamo.internal.weakref_utils import WeakIdSet, supports_weakrefs


class StalenessRegistry:
    # We need to keep track of unlinked values to be able to tell that they are stale now!
    stale_values: WeakIdSet[object]

    def __init__(self):
        super().__init__()
        self.stale_values = WeakIdSet()

    def mark_stale(self, value):
        if supports_weakrefs(value):
            self.stale_values.add(value)

    def mark_used(self, value):
        if supports_weakrefs(value):
            self.stale_values.discard(value)

    def is_stale(self, value):
        return value in self.stale_values
