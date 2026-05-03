import shlex
from dataclasses import dataclass
from typing import Iterable

from gitscript.commit_range import CommitRange
from gitscript.refs import BranchRef, ConstantOffsetRef, DynamicOffsetRef, HeadRef, Ref
from gitscript.operators import Operator
from gitscript.statements import (
    Branch,
    Checkout,
    CherryPick,
    CherryPickRange,
    Commit,
    CommitString,
    Conflict,
    DeleteBranches,
    DeleteTags,
    Log,
    LogRange,
    Merge,
    Rebase,
    Revert,
    RevertRange,
    Reset,
    RevList,
    RevListRange,
    Show,
    Statement,
    Tag,
)


class ParseError(ValueError):
    pass


class IncompleteInput(ParseError):
    pass


@dataclass
class _Line:
    number: int
    text: str


def parse(source: str | Iterable[str]) -> list[Statement]:
    if isinstance(source, str):
        raw_lines = source.splitlines()
    else:
        raw_lines = list(source)

    lines = [_Line(i + 1, line.rstrip("\n")) for i, line in enumerate(raw_lines)]
    parser = _Parser(lines)
    return parser.parse_program()


def parse_repl(source: str | Iterable[str]) -> list[Statement]:
    if isinstance(source, str):
        raw_lines = source.splitlines()
    else:
        raw_lines = list(source)

    lines = [_Line(i + 1, line.rstrip("\n")) for i, line in enumerate(raw_lines)]
    parser = _Parser(lines, allow_incomplete=True)
    return parser.parse_program()


class _Parser:
    def __init__(self, lines: list[_Line], allow_incomplete: bool = False):
        self.lines = lines
        self.index = 0
        self.allow_incomplete = allow_incomplete

    def parse_program(self) -> list[Statement]:
        statements = self._parse_block()
        if (line := self._current()) is not None:
            raise self._error(line, f"Unexpected control-flow marker: {line.text.strip()}")
        return statements

    def _parse_block(self, stop_markers: tuple[str, ...] = ()) -> list[Statement]:
        statements: list[Statement] = []

        while (line := self._current()) is not None:
            stripped = line.text.strip()
            if not stripped or _is_comment(stripped):
                self.index += 1
                continue

            if any(stripped.startswith(marker) for marker in stop_markers):
                break

            if stripped.startswith("<<<<<<<"):
                statements.append(self._parse_conflict(line))
                continue

            if stripped.startswith(("=======", ">>>>>>>")):
                break

            statements.append(_parse_statement(line))
            self.index += 1

        return statements

    def _parse_conflict(self, start: _Line) -> Conflict:
        ref_a_text = start.text.strip()[7:].strip()
        if not ref_a_text:
            raise self._error(start, "Conflict start marker needs a commit reference")

        self.index += 1
        block_a = self._parse_block(("=======",))

        middle = self._current()
        if middle is None or not middle.text.strip().startswith("======="):
            if self.allow_incomplete and middle is None:
                raise IncompleteInput(f"Line {start.number}: Conflict block is missing =======")
            raise self._error(start, "Conflict block is missing =======")

        self.index += 1
        block_b = self._parse_block((">>>>>>>",))

        end = self._current()
        if end is None or not end.text.strip().startswith(">>>>>>>"):
            if self.allow_incomplete and end is None:
                raise IncompleteInput(f"Line {start.number}: Conflict block is missing >>>>>>>")
            raise self._error(start, "Conflict block is missing >>>>>>>")

        ref_b_text = end.text.strip()[7:].strip()
        if not ref_b_text:
            raise self._error(end, "Conflict end marker needs a commit reference")

        self.index += 1
        return Conflict(_parse_ref(ref_a_text, start.number), block_a, _parse_ref(ref_b_text, end.number), block_b)

    def _current(self) -> _Line | None:
        if self.index >= len(self.lines):
            return None
        return self.lines[self.index]

    @staticmethod
    def _error(line: _Line, message: str) -> ParseError:
        return ParseError(f"Line {line.number}: {message}")


def _parse_statement(line: _Line) -> Statement:
    raw = _strip_comment(line.text).strip()

    if _is_commit_string_input(raw):
        if "--amend" in raw.split():
            raise ParseError(f"Line {line.number}: --amend is not allowed for string input commit")
        return CommitString(None)

    try:
        parts = shlex.split(raw, posix=True)
    except ValueError as exc:
        raise ParseError(f"Line {line.number}: {exc}") from exc

    if len(parts) < 2 or parts[0] != "git":
        raise ParseError(f"Line {line.number}: Expected a git command")

    command = parts[1]
    args = parts[2:]

    if command == "commit":
        return _parse_commit(args, line.number, _commit_message_is_quoted(raw))
    if command == "branch":
        return _parse_branch(args, line.number)
    if command == "checkout":
        if len(args) in {2, 3} and args[0] == "-b":
            return Checkout(args[1], _parse_ref(args[2], line.number) if len(args) == 3 else HeadRef())
        _expect_count(args, 1, line.number, "git checkout")
        return Checkout(args[0])
    if command == "reset":
        _expect_count(args, 1, line.number, "git reset")
        return Reset(_parse_ref(args[0], line.number))
    if command == "merge":
        return _parse_merge(args, line.number)
    if command == "cherry-pick":
        _expect_count(args, 1, line.number, "git cherry-pick")
        target = _parse_range_or_ref(args[0], line.number)
        if isinstance(target, CommitRange):
            return CherryPickRange(target)
        return CherryPick(target)
    if command == "revert":
        _expect_count(args, 1, line.number, "git revert")
        target = _parse_range_or_ref(args[0], line.number)
        if isinstance(target, CommitRange):
            return RevertRange(target)
        return Revert(target)
    if command == "rebase":
        _expect_count(args, 1, line.number, "git rebase")
        return Rebase(_parse_ref(args[0], line.number))
    if command == "tag":
        return _parse_tag(args, line.number)
    if command == "show":
        _expect_count(args, (0, 1), line.number, "git show")
        return Show(_parse_ref(args[0], line.number) if args else HeadRef())
    if command == "log":
        target, limit, reverse = _parse_list_args(args, line.number, "git log")
        if isinstance(target, CommitRange):
            return LogRange(target, limit, reverse)
        return Log(target, limit, reverse)
    if command == "rev-list":
        target, limit, reverse = _parse_list_args(args, line.number, "git rev-list")
        if isinstance(target, CommitRange):
            return RevListRange(target, limit, reverse)
        return RevList(target, limit, reverse)

    raise ParseError(f"Line {line.number}: Unknown git command: {command}")


def _parse_branch(args: list[str], line_number: int) -> Statement:
    if args and args[0] == "-d":
        if len(args) < 2:
            raise ParseError(f"Line {line_number}: git branch -d needs at least one branch name")
        return DeleteBranches(args[1:])

    _expect_count(args, (1, 2), line_number, "git branch")
    return Branch(args[0], _parse_ref(args[1], line_number) if len(args) == 2 else HeadRef())


def _parse_tag(args: list[str], line_number: int) -> Statement:
    if args and args[0] == "-d":
        if len(args) < 2:
            raise ParseError(f"Line {line_number}: git tag -d needs at least one tag name")
        return DeleteTags(args[1:])

    _expect_count(args, 1, line_number, "git tag")
    return Tag(args[0])


def _parse_commit(args: list[str], line_number: int, message_is_quoted: bool) -> Statement:
    amend = False
    value_seen = False
    value: int | str | None = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--amend":
            amend = True
            i += 1
        elif arg == "-m":
            if value_seen:
                raise ParseError(f"Line {line_number}: git commit accepts only one -m value")
            if i + 1 >= len(args):
                raise ParseError(f"Line {line_number}: git commit -m needs a value")
            value = args[i + 1]
            value_seen = True
            i += 2
        elif arg.startswith("-m="):
            if value_seen:
                raise ParseError(f"Line {line_number}: git commit accepts only one -m value")
            value = arg[3:]
            value_seen = True
            i += 1
        else:
            raise ParseError(f"Line {line_number}: Unexpected git commit argument: {arg}")

    if not value_seen:
        return Commit(None, amend)

    if message_is_quoted:
        if amend:
            raise ParseError(f"Line {line_number}: --amend is not allowed for string commits")
        return CommitString(str(value))

    try:
        return Commit(int(value), amend)
    except ValueError as exc:
        raise ParseError(f"Line {line_number}: git commit -m needs an integer or quoted string") from exc


def _parse_merge(args: list[str], line_number: int) -> Merge:
    if not args:
        raise ParseError(f"Line {line_number}: git merge needs a commit reference")

    ref_text = args[0]
    op = Operator.ADD
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "-s":
            if i + 1 >= len(args):
                raise ParseError(f"Line {line_number}: git merge -s needs a strategy")
            op = _parse_operator(args[i + 1], line_number)
            i += 2
        elif arg.startswith("-s="):
            op = _parse_operator(arg[3:], line_number)
            i += 1
        else:
            raise ParseError(f"Line {line_number}: Unexpected git merge argument: {arg}")

    return Merge(_parse_ref(ref_text, line_number), op)


def _parse_operator(text: str, line_number: int) -> Operator:
    for op in Operator:
        if op.value == text:
            return op
    raise ParseError(f"Line {line_number}: Unknown merge strategy: {text}")


def _parse_range_or_ref(text: str, line_number: int) -> Ref | CommitRange:
    if ".." in text:
        parts = text.split("..")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ParseError(f"Line {line_number}: Invalid commit range: {text}")
        return CommitRange(_parse_ref(parts[0], line_number), _parse_ref(parts[1], line_number))
    return _parse_ref(text, line_number)


def _parse_list_args(args: list[str], line_number: int, command: str) -> tuple[Ref | CommitRange, int | None, bool]:
    limit = None
    reverse = False
    target: Ref | CommitRange | None = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--reverse":
            reverse = True
            i += 1
        elif arg == "-n":
            if i + 1 >= len(args):
                raise ParseError(f"Line {line_number}: {command} -n needs a limit")
            limit = _parse_limit(args[i + 1], line_number, command)
            i += 2
        elif arg.startswith("-n="):
            limit = _parse_limit(arg[3:], line_number, command)
            i += 1
        elif arg.startswith("-"):
            raise ParseError(f"Line {line_number}: Unexpected {command} argument: {arg}")
        else:
            if target is not None:
                raise ParseError(f"Line {line_number}: {command} accepts only one ref or range")
            target = _parse_range_or_ref(arg, line_number)
            i += 1

    return target if target is not None else HeadRef(), limit, reverse


def _parse_limit(text: str, line_number: int, command: str) -> int:
    try:
        limit = int(text)
    except ValueError as exc:
        raise ParseError(f"Line {line_number}: {command} -n needs a non-negative integer") from exc

    if limit < 0:
        raise ParseError(f"Line {line_number}: {command} -n needs a non-negative integer")
    return limit


def _parse_ref(text: str, line_number: int) -> Ref:
    tokens = _RefTokens(text, line_number)
    ref = _parse_ref_expr(tokens)
    if not tokens.done:
        raise ParseError(f"Line {line_number}: Unexpected token in commit reference: {tokens.peek()}")
    return ref


def _parse_ref_expr(tokens: "_RefTokens") -> Ref:
    base = _parse_ref_atom(tokens)
    if tokens.accept("~"):
        offset = _parse_ref_expr(tokens)
        if isinstance(offset, BranchRef) and offset.name.isdecimal():
            return ConstantOffsetRef(base, int(offset.name))
        return DynamicOffsetRef(base, offset)
    return base


def _parse_ref_atom(tokens: "_RefTokens") -> Ref:
    token = tokens.next()
    if token is None:
        raise ParseError(f"Line {tokens.line_number}: Expected commit reference")
    if token == "HEAD":
        return HeadRef()
    if token == "(":
        ref = _parse_ref_expr(tokens)
        if not tokens.accept(")"):
            raise ParseError(f"Line {tokens.line_number}: Missing ')' in commit reference")
        return ref
    if token in {"~", ")"}:
        raise ParseError(f"Line {tokens.line_number}: Expected commit reference before {token}")
    return BranchRef(token)


class _RefTokens:
    def __init__(self, text: str, line_number: int):
        self.tokens = _tokenize_ref(text, line_number)
        self.line_number = line_number
        self.index = 0

    @property
    def done(self) -> bool:
        return self.index >= len(self.tokens)

    def peek(self) -> str | None:
        if self.done:
            return None
        return self.tokens[self.index]

    def next(self) -> str | None:
        token = self.peek()
        if token is not None:
            self.index += 1
        return token

    def accept(self, expected: str) -> bool:
        if self.peek() == expected:
            self.index += 1
            return True
        return False


def _tokenize_ref(text: str, line_number: int) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char.isspace():
            i += 1
            continue
        if char in "()~":
            tokens.append(char)
            i += 1
            continue

        start = i
        while i < len(text) and not text[i].isspace() and text[i] not in "()~":
            i += 1
        token = text[start:i]
        if token.startswith("-"):
            raise ParseError(f"Line {line_number}: Negative offsets are not valid syntax")
        tokens.append(token)

    if not tokens:
        raise ParseError(f"Line {line_number}: Expected commit reference")
    return tokens


def _strip_comment(text: str) -> str:
    in_quote = False
    escaped = False
    for i, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if char == "#" and not in_quote:
            return text[:i]
    return text


def _is_commit_string_input(text: str) -> bool:
    message_start = _commit_message_start(text)
    if message_start is None or message_start >= len(text):
        return False
    return text[message_start] == '"' and not _has_closing_quote(text, message_start)


def _commit_message_is_quoted(text: str) -> bool:
    message_start = _commit_message_start(text)
    return message_start is not None and message_start < len(text) and text[message_start] == '"'


def _commit_message_start(text: str) -> int | None:
    try:
        parts = shlex.split(text, posix=False)
    except ValueError:
        parts = text.split()

    if len(parts) < 3 or parts[0] != "git" or parts[1] != "commit":
        return None

    index = text.find("-m")
    while index != -1:
        before_ok = index == 0 or text[index - 1].isspace()
        after = index + 2
        after_ok = after == len(text) or text[after].isspace() or text[after] == "="
        if before_ok and after_ok:
            if after < len(text) and text[after] == "=":
                return after + 1
            while after < len(text) and text[after].isspace():
                after += 1
            return after
        index = text.find("-m", index + 1)

    return None


def _has_closing_quote(text: str, quote_index: int) -> bool:
    escaped = False
    for char in text[quote_index + 1 :]:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            return True
    return False


def _is_comment(stripped: str) -> bool:
    return stripped.startswith("#")


def _expect_count(args: list[str], expected: int | tuple[int, ...], line_number: int, command: str) -> None:
    if isinstance(expected, int):
        expected_counts = (expected,)
    else:
        expected_counts = expected

    if len(args) not in expected_counts:
        if len(expected_counts) == 1:
            message = f"{command} expects {expected_counts[0]} argument(s)"
        else:
            message = f"{command} expects {' or '.join(str(count) for count in expected_counts)} argument(s)"
        raise ParseError(f"Line {line_number}: {message}")
