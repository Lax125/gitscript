from enum import Enum


class Operator(Enum):
    OURS = "ours"
    THEIRS = "theirs"
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
