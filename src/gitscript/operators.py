from enum import Enum


class Operator(Enum):
    OURS = "ours"
    THEIRS = "theirs"
    MIN = "min"
    MAX = "max"
    ADD = "add"
    SUBTRACT = "sub"
    MULTIPLY = "mul"
    DIVIDE = "div"
    MODULO = "mod"
    GT = "gt"
    LT = "lt"
    EQ = "eq"
    NEQ = "neq"
    GTE = "gte"
    LTE = "lte"


class Condition(Enum):
    GT = "gt"
    LT = "lt"
    EQ = "eq"
    NEQ = "neq"
    GTE = "gte"
    LTE = "lte"
    IS = "is"
