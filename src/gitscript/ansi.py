import re


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"

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
BINDING = DIM

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def paint(text: object, color: str) -> str:
    return f"{color}{text}{RESET}"


def strip(text: str) -> str:
    return _ANSI_RE.sub("", text)
