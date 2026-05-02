class Commit:
    __slots__ = ("value", "parent")

    def __init__(self, value, parent=None):
        self.value = value
        self.parent = parent
