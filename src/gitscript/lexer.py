from dataclasses import dataclass
from enum import Enum, auto


_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_/")


class LexError(ValueError):
    pass


class TokenKind(Enum):
    WORD = auto()
    STRING_LITERAL = auto()
    INT_LITERAL = auto()
    LABEL = auto()
    OPTION = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    line: int
    column: int
    quoted: bool = False
    quote: str | None = None


def lex_statement(text: str, line_number: int) -> list[Token]:
    tokens: list[Token] = []
    i = 0

    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        if text[i] == "#":
            break

        column = i + 1
        value, quote, i = _read_token(text, i, line_number)
        quoted = quote is not None
        tokens.append(Token(_classify(value, quoted), value, line_number, column, quoted, quote))

    return tokens


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


def _read_token(text: str, start: int, line_number: int) -> tuple[str, str | None, int]:
    pieces: list[str] = []
    quote: str | None = None
    i = start

    while i < len(text):
        char = text[i]
        if char.isspace() or char == "#":
            break
        if text.startswith('"""', i):
            quote = '"""'
            value, i = _read_triple_string(text, i + 3, line_number)
            pieces.append(value)
            continue
        if char == '"':
            quote = quote or '"'
            value, i = _read_double_string(text, i + 1, line_number)
            pieces.append(value)
            continue
        if char == "'":
            quote = quote or "'"
            value, i = _read_single_string(text, i + 1, line_number)
            pieces.append(value)
            continue

        pieces.append(char)
        i += 1

    return "".join(pieces), quote, i


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


def _classify(value: str, quoted: bool) -> TokenKind:
    if quoted:
        return TokenKind.STRING_LITERAL
    if value in {"true", "false"} or _is_decimal_integer(value):
        return TokenKind.INT_LITERAL
    if value.startswith("-"):
        return TokenKind.OPTION
    if value and all(char in _NAME_CHARS for char in value):
        return TokenKind.LABEL
    return TokenKind.WORD


def _is_decimal_integer(value: str) -> bool:
    if value.startswith("-"):
        return value[1:].isdecimal()
    return value.isdecimal()
