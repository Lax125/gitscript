import re


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"

RED = "\033[1;31m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[1;34m"
MAGENTA = "\033[1;35m"
CYAN = "\033[1;36m"

DARK_YELLOW = "\033[0;33m"
DARK_CYAN = "\033[0;36m"

BRANCH = BOLD + GREEN
TAG = BOLD + MAGENTA
PARAM = BOLD + BLUE
COMMIT = BOLD + CYAN
VALUE = BOLD + YELLOW
CHAR = BOLD + BLUE
DEBUG = BOLD + RED
MERGE = BOLD + MAGENTA
PROTECTED = BOLD + RED
GRAPH = DIM
BINDING_SEPARATOR = ""
BINDING = ITALIC
SHORTFORM = BOLD + DARK_YELLOW
FUNCTION = BOLD + DARK_CYAN

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def paint(text: object, color: str) -> str:
    return f"{color}{text}{RESET}"


def strip(text: str) -> str:
    return _ANSI_RE.sub("", text)
