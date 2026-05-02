class Commit:
    __slots__ = ("value", "parent", "refcount")

    def __init__(self, value, parent=None):
        self.value = value
        self.parent = parent
        self.refcount = 0  # for GC