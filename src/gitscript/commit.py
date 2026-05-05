class Commit:
    __slots__ = ("value", "parent", "order")

    def __init__(self, value, parent=None, order: int = -1):
        self.value = value
        self.parent = parent
        self.order = order
