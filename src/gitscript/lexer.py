from dataclasses import dataclass
from enum import Enum, auto


_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_/")
_WORD_BREAKS = frozenset("()~=<>!+*%")


class LexError(ValueError):
    pass


class TokenKind(Enum):
    IDENTIFIER = auto()
    STRING_LITERAL = auto()
    INT_LITERAL = auto()

    GIT = auto()
    COMMIT = auto()
    BRANCH = auto()
    CHECKOUT = auto()
    CONFIG = auto()
    RESET = auto()
    MERGE = auto()
    CHERRY_PICK = auto()
    REVERT = auto()
    REBASE = auto()
    TAG = auto()
    SHOW = auto()
    LOG = auto()
    REV_LIST = auto()
    EXIT = auto()
    HEAD = auto()

    OPTION = auto()
    CONFIG_KEY = auto()

    AND = auto()
    NEWLINE = auto()
    LPAREN = auto()
    RPAREN = auto()
    EQUALS = auto()
    TILDE = auto()
    RANGE = auto()
    CONFLICT_START = auto()
    CONFLICT_MIDDLE = auto()
    CONFLICT_END = auto()

    STRATEGY_ADD = auto()
    STRATEGY_SUBTRACT = auto()
    STRATEGY_MULTIPLY = auto()
    STRATEGY_DIVIDE = auto()
    STRATEGY_MODULO = auto()
    STRATEGY_GT = auto()
    STRATEGY_LT = auto()
    STRATEGY_GTE = auto()
    STRATEGY_LTE = auto()
    STRATEGY_EQ = auto()
    STRATEGY_NEQ = auto()
    STRATEGY_OURS = auto()
    STRATEGY_THEIRS = auto()
    STRATEGY_MIN = auto()
    STRATEGY_MAX = auto()
    STRATEGY_IS = auto()

    UNKNOWN = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    line: int
    column: int
    quoted: bool = False
    quote: str | None = None
    group: int = 0


_KEYWORDS = {
    "git": TokenKind.GIT,
    "commit": TokenKind.COMMIT,
    "branch": TokenKind.BRANCH,
    "checkout": TokenKind.CHECKOUT,
    "config": TokenKind.CONFIG,
    "reset": TokenKind.RESET,
    "merge": TokenKind.MERGE,
    "cherry-pick": TokenKind.CHERRY_PICK,
    "revert": TokenKind.REVERT,
    "rebase": TokenKind.REBASE,
    "tag": TokenKind.TAG,
    "show": TokenKind.SHOW,
    "log": TokenKind.LOG,
    "rev-list": TokenKind.REV_LIST,
    "exit": TokenKind.EXIT,
    "HEAD": TokenKind.HEAD,
}

_WORD_STRATEGIES = {
    "ours": TokenKind.STRATEGY_OURS,
    "theirs": TokenKind.STRATEGY_THEIRS,
    "min": TokenKind.STRATEGY_MIN,
    "max": TokenKind.STRATEGY_MAX,
    "is": TokenKind.STRATEGY_IS,
}

_SYMBOL_TOKENS = {
    "&&": TokenKind.AND,
    "<<<<<<<": TokenKind.CONFLICT_START,
    "=======": TokenKind.CONFLICT_MIDDLE,
    ">>>>>>>": TokenKind.CONFLICT_END,
    "..": TokenKind.RANGE,
    ">=": TokenKind.STRATEGY_GTE,
    "<=": TokenKind.STRATEGY_LTE,
    "==": TokenKind.STRATEGY_EQ,
    "!=": TokenKind.STRATEGY_NEQ,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    "=": TokenKind.EQUALS,
    "~": TokenKind.TILDE,
    "+": TokenKind.STRATEGY_ADD,
    "-": TokenKind.STRATEGY_SUBTRACT,
    "*": TokenKind.STRATEGY_MULTIPLY,
    "/": TokenKind.STRATEGY_DIVIDE,
    "%": TokenKind.STRATEGY_MODULO,
    ">": TokenKind.STRATEGY_GT,
    "<": TokenKind.STRATEGY_LT,
}

_SEPARATOR_KINDS = frozenset({
    TokenKind.AND,
    TokenKind.NEWLINE,
    TokenKind.CONFLICT_START,
    TokenKind.CONFLICT_MIDDLE,
    TokenKind.CONFLICT_END,
})


def lex_statement(text: str, line_number: int) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    group = -1
    after_whitespace = True
    current_line = line_number
    current_column = 1

    while i < len(text):
        if text.startswith("\r\n", i):
            group += 1
            tokens.append(Token(TokenKind.NEWLINE, "\n", current_line, current_column, group=group))
            i += 2
            current_line += 1
            current_column = 1
            group += 1
            after_whitespace = True
            continue
        if text[i] == "\n":
            group += 1
            tokens.append(Token(TokenKind.NEWLINE, "\n", current_line, current_column, group=group))
            i += 1
            current_line += 1
            current_column = 1
            group += 1
            after_whitespace = True
            continue
        if text[i].isspace():
            after_whitespace = True
            i += 1
            current_column += 1
            continue
        if text[i] == "#":
            while i < len(text) and text[i] not in "\r\n":
                i += 1
                current_column += 1
            continue

        if after_whitespace:
            group += 1
            after_whitespace = False

        token_start = i
        token, i = _read_next_token(text, i, current_line, current_column, group)
        tokens.append(token)
        consumed = text[token_start:i]
        current_line += consumed.count("\n")
        if "\n" in consumed:
            current_column = len(consumed.rsplit("\n", 1)[-1]) + 1
        else:
            current_column += len(consumed)

    return tokens


def is_identifier_text(value: str) -> bool:
    return _classify_word(value) == TokenKind.IDENTIFIER


def is_separator_token(token: Token) -> bool:
    return token.kind in _SEPARATOR_KINDS


def strip_comment(text: str) -> str:
    in_single_quote = False
    in_double_quote = False
    escaped = False
    i = 0

    while i < len(text):
        if text.startswith('"""', i) and not in_single_quote and not in_double_quote:
            i = _skip_triple_string(text, i + 3)
            continue

        char = text[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if char == "\\":
            escaped = True
            i += 1
            continue
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            i += 1
            continue
        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            i += 1
            continue
        if char == "#" and not in_double_quote and not in_single_quote:
            return text[:i]
        i += 1

    return text


def _read_next_token(text: str, start: int, line_number: int, column: int, group: int) -> tuple[Token, int]:
    if text.startswith('"""', start):
        value, end = _read_triple_string(text, start + 3, line_number)
        return Token(TokenKind.STRING_LITERAL, value, line_number, column, True, '"""', group), end
    if text[start] == '"':
        value, end = _read_double_string(text, start + 1, line_number)
        return Token(TokenKind.STRING_LITERAL, value, line_number, column, True, '"', group), end
    if text[start] == "'":
        value, end = _read_single_string(text, start + 1, line_number)
        return Token(TokenKind.STRING_LITERAL, value, line_number, column, True, "'", group), end

    for symbol in sorted(_SYMBOL_TOKENS, key=len, reverse=True):
        if symbol == "-" and start + 1 < len(text) and not text[start + 1].isspace():
            continue
        if text.startswith(symbol, start):
            return Token(_SYMBOL_TOKENS[symbol], symbol, line_number, column, group=group), start + len(symbol)

    value, end = _read_word(text, start)
    return Token(_classify_word(value), value, line_number, column, group=group), end


def _read_word(text: str, start: int) -> tuple[str, int]:
    i = start
    while i < len(text):
        if text[i].isspace() or text[i] == "#":
            break
        if text.startswith("&&", i) or text.startswith("..", i):
            break
        if any(text.startswith(marker, i) for marker in ("<<<<<<<", "=======", ">>>>>>>")):
            break
        if text[i] in _WORD_BREAKS:
            break
        if text[i] == "/" and (i == start or i + 1 == len(text) or text[i + 1].isspace()):
            break
        i += 1
    return text[start:i], i


def _read_double_string(text: str, i: int, line_number: int) -> tuple[str, int]:
    pieces: list[str] = []
    escaped = False

    while i < len(text):
        char = text[i]
        if escaped:
            pieces.append(char)
            escaped = False
            i += 1
            continue
        if char == "\\":
            escaped = True
            i += 1
            continue
        if char == '"':
            return "".join(pieces), i + 1
        pieces.append(char)
        i += 1

    raise LexError(f"Line {line_number}: No closing quotation")


def _read_single_string(text: str, i: int, line_number: int) -> tuple[str, int]:
    closing = text.find("'", i)
    if closing == -1:
        raise LexError(f"Line {line_number}: No closing quotation")
    return text[i:closing], closing + 1


def _read_triple_string(text: str, i: int, line_number: int) -> tuple[str, int]:
    closing = text.find('"""', i)
    if closing == -1:
        raise LexError(f"Line {line_number}: triple-quoted string is missing closing quote")
    return text[i:closing], closing + 3


def _skip_triple_string(text: str, i: int) -> int:
    closing = text.find('"""', i)
    if closing == -1:
        return len(text)
    return closing + 3


def _classify_word(value: str) -> TokenKind:
    if value in {"true", "false"} or _is_decimal_integer(value):
        return TokenKind.INT_LITERAL
    if value in _KEYWORDS:
        return _KEYWORDS[value]
    if value in _WORD_STRATEGIES:
        return _WORD_STRATEGIES[value]
    if value.startswith("-"):
        return TokenKind.OPTION
    if "." in value:
        return TokenKind.CONFIG_KEY
    if value and all(char in _NAME_CHARS for char in value):
        return TokenKind.IDENTIFIER
    return TokenKind.UNKNOWN


def _is_decimal_integer(value: str) -> bool:
    if value.startswith("-"):
        return value[1:].isdecimal()
    return value.isdecimal()
