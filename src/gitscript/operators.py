from enum import Enum


class Operator(Enum):
    OURS = "ours"
    THEIRS = "theirs"
    MIN = "min"
    MAX = "max"
    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"
    MODULO = "%"
    GT = ">"
    LT = "<"
    EQ = "=="
    NEQ = "!="
    GTE = ">="
    LTE = "<="


class Condition(Enum):
    GT = ">"
    LT = "<"
    EQ = "=="
    NEQ = "!="
    GTE = ">="
    LTE = "<="
    IS = "is"
