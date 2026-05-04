import shlex
import re
from dataclasses import dataclass
from typing import Iterable

from gitscript.commit_range import CommitRange
from gitscript.refs import BranchRef, ConstantOffsetRef, DynamicOffsetRef, HeadRef, Ref
from gitscript.operators import Condition, Operator
from gitscript.statements import (
    Branch,
    Checkout,
    CherryPick,
    CherryPickRange,
    Commit,
    CommitString,
    Config,
    Conflict,
    AliasCall,
    DefineAlias,
    DefineFunction,
    DeleteBranches,
    DeleteTags,
    Exit,
    ListBranches,
    Log,
    LogRange,
    MergeAbort,
    MergeContinue,
    Rebase,
    Revert,
    RevertRange,
    Reset,
    RevList,
    RevListRange,
    Show,
    Statement,
    Tag,
    Parameter,
)


_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_/")


class ParseError(ValueError):
    pass


class IncompleteInput(ParseError):
    pass


@dataclass
class _Line:
    number: int
    text: str


@dataclass
class _MergeStart:
    condition: Condition
    label: str | None = None


def _prepare_lines(raw_lines: list[str], allow_incomplete: bool) -> list[_Line]:
    lines: list[_Line] = []
    i = 0

    while i < len(raw_lines):
        line_number = i + 1
        text = raw_lines[i].rstrip("\n")

        if _is_multiline_alias_start(text):
            collected = [text]
            while _has_unclosed_single_quote("\n".join(collected)):
                i += 1
                if i >= len(raw_lines):
                    message = f"Line {line_number}: git config alias is missing closing quote"
                    if allow_incomplete:
                        raise IncompleteInput(message)
                    raise ParseError(message)
                collected.append(raw_lines[i].rstrip("\n"))
            lines.append(_Line(line_number, "\n".join(collected)))
        elif _is_triple_commit_string_start(text) or _has_unclosed_triple_quote(text):
            collected = [text]
            while _has_unclosed_triple_quote("\n".join(collected)):
                i += 1
                if i >= len(raw_lines):
                    message = f"Line {line_number}: triple-quoted string is missing closing quote"
                    if allow_incomplete:
                        raise IncompleteInput(message)
                    raise ParseError(message)
                collected.append(raw_lines[i].rstrip("\n"))
            lines.append(_Line(line_number, "\n".join(collected)))
        else:
            parts = _split_statement_separators(text)
            if len(parts) > 1 and any(_is_conflict_marker(part.strip()) for part in parts):
                raise ParseError(f"Line {line_number}: Conflict markers cannot share a line with &&")
            lines.extend(_Line(line_number, part) for part in parts)

        i += 1

    return lines


def parse(source: str | Iterable[str]) -> list[Statement]:
    if isinstance(source, str):
        raw_lines = source.splitlines()
    else:
        raw_lines = list(source)

    lines = _prepare_lines(raw_lines, allow_incomplete=False)
    parser = _Parser(lines)
    return parser.parse_program()


def parse_repl(source: str | Iterable[str]) -> list[Statement]:
    if isinstance(source, str):
        raw_lines = source.splitlines()
    else:
        raw_lines = list(source)

    lines = _prepare_lines(raw_lines, allow_incomplete=True)
    parser = _Parser(lines, allow_incomplete=True)
    return parser.parse_program()


def validate_function_body(body: str, parameters: list[Parameter]) -> None:
    parameter_kinds = {parameter.name: parameter.kind for parameter in parameters}
    lines = _prepare_lines(body.splitlines(), allow_incomplete=False)
    _validate_function_statement_starts(lines)
    _validate_function_parameter_uses(lines, parameter_kinds)
    parse(_substitute_function_parameter_placeholders(body, parameter_kinds))


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
                raise self._error(line, "Conflict block must be preceded by git merge")

            if stripped.startswith(("=======", ">>>>>>>")):
                break

            statement = _parse_statement(line)
            self.index += 1
            if isinstance(statement, _MergeStart):
                self._skip_ignored_lines()
                conflict_start = self._current()
                if conflict_start is None:
                    if self.allow_incomplete:
                        raise IncompleteInput(f"Line {line.number}: git merge needs a conflict block")
                    raise self._error(line, "git merge needs a conflict block")
                if not conflict_start.text.strip().startswith("<<<<<<<"):
                    raise self._error(conflict_start, "git merge must be followed by a conflict block")
                statements.append(self._parse_conflict(conflict_start, statement.condition, statement.label))
            else:
                statements.append(statement)

        return statements

    def _parse_conflict(self, start: _Line, condition: Condition, label: str | None) -> Conflict:
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
        return Conflict(
            _parse_ref(ref_a_text, start.number),
            _parse_ref(ref_b_text, end.number),
            block_a,
            block_b,
            condition,
            label,
        )

    def _current(self) -> _Line | None:
        if self.index >= len(self.lines):
            return None
        return self.lines[self.index]

    def _skip_ignored_lines(self) -> None:
        while (line := self._current()) is not None:
            stripped = line.text.strip()
            if stripped and not _is_comment(stripped):
                return
            self.index += 1

    @staticmethod
    def _error(line: _Line, message: str) -> ParseError:
        return ParseError(f"Line {line.number}: {message}")


def _parse_statement(line: _Line) -> Statement | _MergeStart:
    triple_commit = _parse_triple_commit_string(line.text, line.number)
    if triple_commit is not None:
        return triple_commit

    raw = _strip_comment(line.text).strip()

    if raw == "exit":
        return Exit()

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
            return Checkout(
                _parse_name(args[1], line.number, "branch"),
                _parse_ref(args[2], line.number) if len(args) == 3 else HeadRef(),
            )
        _expect_count(args, 1, line.number, "git checkout")
        return Checkout(_parse_name(args[0], line.number, "branch"))
    if command == "config":
        return _parse_config(args, line.number)
    if command == "reset":
        _expect_count(args, 1, line.number, "git reset")
        return Reset(_parse_ref(args[0], line.number))
    if command == "merge":
        return _parse_merge(args, line.number)
    if command == "cherry-pick":
        return _parse_cherry_pick(args, line.number)
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

    return AliasCall(command, args)


def _parse_branch(args: list[str], line_number: int) -> Statement:
    if not args:
        return ListBranches()

    if args and args[0] == "-d":
        if len(args) < 2:
            raise ParseError(f"Line {line_number}: git branch -d needs at least one branch name")
        return DeleteBranches([_parse_name(name, line_number, "branch") for name in args[1:]])

    _expect_count(args, (1, 2), line_number, "git branch")
    return Branch(_parse_name(args[0], line_number, "branch"), _parse_ref(args[1], line_number) if len(args) == 2 else HeadRef())


def _parse_tag(args: list[str], line_number: int) -> Statement:
    if args and args[0] == "-d":
        if len(args) < 2:
            raise ParseError(f"Line {line_number}: git tag -d needs at least one tag name")
        return DeleteTags([_parse_name(name, line_number, "tag") for name in args[1:]])

    _expect_count(args, 1, line_number, "git tag")
    return Tag(_parse_name(args[0], line_number, "tag"))


def _parse_config(args: list[str], line_number: int) -> Statement:
    if not args:
        raise ParseError(f"Line {line_number}: git config expects a key")

    if args[0].startswith("alias."):
        return _parse_alias_config(args, line_number)

    _expect_count(args, 2, line_number, "git config")

    key, value = args
    if key == "commit.verbose":
        return Config(key, _parse_integer_literal(value, line_number, "commit.verbose"))

    if key == "merge.verbosity":
        try:
            verbosity = int(value)
        except ValueError as exc:
            raise ParseError(f"Line {line_number}: merge.verbosity must be 0, 1, or 2") from exc
        if verbosity not in {0, 1, 2}:
            raise ParseError(f"Line {line_number}: merge.verbosity must be 0, 1, or 2")
        return Config(key, verbosity)

    raise ParseError(f"Line {line_number}: Unknown config key: {key}")


def _parse_alias_config(args: list[str], line_number: int) -> DefineAlias | DefineFunction:
    key = args[0]
    name = key[len("alias."):]
    _parse_name(name, line_number, "alias")

    if len(args) < 2:
        raise ParseError(f"Line {line_number}: git config alias needs a value")

    parameters: list[Parameter] = []
    i = 1
    while i < len(args) - 1:
        kind = args[i]
        if kind not in {"-i", "-s", "-l", "-b", "-p", "-t", "-r", "-c", "-o"}:
            raise ParseError(f"Line {line_number}: Unknown function parameter type: {kind}")
        parameter_text = args[i + 1]
        parameter_name, default = _parse_parameter(parameter_text, kind, line_number)
        parameters.append(Parameter(kind, parameter_name, default))
        i += 2

    if i != len(args) - 1:
        raise ParseError(f"Line {line_number}: Function parameter needs a name")

    value = args[-1]
    if value.startswith("!"):
        return DefineFunction(name, parameters, value[1:])

    if parameters:
        raise ParseError(f"Line {line_number}: Shortform aliases cannot declare parameters")
    return DefineAlias(name, value)


def _parse_parameter(text: str, kind: str, line_number: int) -> tuple[str, str | None]:
    if "=" in text:
        name, default = text.split("=", 1)
    else:
        name, default = text, None

    _parse_name(name, line_number, "parameter")
    if default is not None:
        default = _validate_parameter_default(kind, default, line_number)
    return name, default


def _validate_parameter_default(kind: str, value: str, line_number: int) -> str:
    if kind == "-i":
        return str(_parse_integer_literal(value, line_number, "integer parameter default"))
    if kind == "-s":
        return value
    if kind in {"-l", "-b", "-p", "-t"}:
        return _parse_name(value, line_number, "parameter default")
    if kind == "-r":
        _parse_ref(value, line_number)
        return value
    if kind == "-c":
        _parse_condition(value, line_number)
        return value
    if kind == "-o":
        _parse_operator(value, line_number)
        return value
    raise ParseError(f"Line {line_number}: Unknown function parameter type: {kind}")


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

    return Commit(_parse_integer_literal(str(value), line_number, "git commit -m"), amend)


def _parse_triple_commit_string(text: str, line_number: int) -> CommitString | None:
    message_start = _triple_commit_string_start(text)
    if message_start is None:
        return None

    opening = message_start + 3
    closing = text.find('"""', opening)
    if closing == -1:
        raise ParseError(f"Line {line_number}: triple-quoted git commit string is missing closing quote")

    prefix_parts = shlex.split(text[:message_start], posix=True)
    _validate_triple_commit_prefix(prefix_parts, line_number)

    after = text[closing + 3 :]
    if _strip_comment(after).strip():
        raise ParseError(f"Line {line_number}: Unexpected git commit argument after triple-quoted string")

    return CommitString(text[opening:closing])


def _validate_triple_commit_prefix(parts: list[str], line_number: int) -> None:
    if len(parts) < 3 or parts[0] != "git" or parts[1] != "commit":
        raise ParseError(f"Line {line_number}: Expected a git command")

    value_seen = False
    for arg in parts[2:]:
        if arg == "--amend":
            raise ParseError(f"Line {line_number}: --amend is not allowed for string commits")
        if arg in {"-m", "-m="}:
            if value_seen:
                raise ParseError(f"Line {line_number}: git commit accepts only one -m value")
            value_seen = True
            continue
        raise ParseError(f"Line {line_number}: Unexpected git commit argument: {arg}")

    if not value_seen:
        raise ParseError(f"Line {line_number}: git commit -m needs a value")


def _parse_cherry_pick(args: list[str], line_number: int) -> CherryPick | CherryPickRange:
    if not args:
        raise ParseError(f"Line {line_number}: git cherry-pick needs a commit reference or range")

    op = Operator.THEIRS
    i = 1
    target = _parse_range_or_ref(args[0], line_number)
    while i < len(args):
        arg = args[i]
        if arg == "-s":
            if i + 1 >= len(args):
                raise ParseError(f"Line {line_number}: git cherry-pick -s needs a strategy")
            op = _parse_operator(args[i + 1], line_number)
            i += 2
        elif arg.startswith("-s="):
            op = _parse_operator(arg[3:], line_number)
            i += 1
        else:
            raise ParseError(f"Line {line_number}: Unexpected git cherry-pick argument: {arg}")

    if isinstance(target, CommitRange):
        return CherryPickRange(target, op)
    return CherryPick(target, op)


def _parse_merge(args: list[str], line_number: int) -> Statement | _MergeStart:
    condition = Condition.EQ
    label = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--continue":
            _expect_count(args, (1, 2), line_number, "git merge --continue")
            return MergeContinue(_parse_merge_signal_label(args, line_number, "git merge --continue"))
        if arg == "--abort":
            _expect_count(args, (1, 2), line_number, "git merge --abort")
            return MergeAbort(_parse_merge_signal_label(args, line_number, "git merge --abort"))
        if arg == "-s":
            if i + 1 >= len(args):
                raise ParseError(f"Line {line_number}: git merge -s needs a condition")
            condition = _parse_condition(args[i + 1], line_number)
            i += 2
        elif arg.startswith("-s="):
            condition = _parse_condition(arg[3:], line_number)
            i += 1
        elif arg.startswith("-"):
            raise ParseError(f"Line {line_number}: Unexpected git merge argument: {arg}")
        else:
            if label is not None:
                raise ParseError(f"Line {line_number}: git merge accepts only one label")
            label = arg
            i += 1

    return _MergeStart(condition, label)


def _parse_merge_signal_label(args: list[str], line_number: int, command: str) -> str | None:
    if len(args) == 1:
        return None
    if args[1].startswith("-"):
        raise ParseError(f"Line {line_number}: Unexpected {command} argument: {args[1]}")
    return args[1]


def _parse_operator(text: str, line_number: int) -> Operator:
    for op in Operator:
        if op.value == text:
            return op
    raise ParseError(f"Line {line_number}: Unknown strategy: {text}")


def _parse_condition(text: str, line_number: int) -> Condition:
    for condition in Condition:
        if condition.value == text:
            return condition
    raise ParseError(f"Line {line_number}: Unknown merge condition: {text}")


def _parse_name(text: str, line_number: int, kind: str) -> str:
    if text == "HEAD":
        raise ParseError(f"Line {line_number}: {kind} name cannot be HEAD")
    if text.startswith("-"):
        raise ParseError(f"Line {line_number}: {kind} name cannot start with -")
    if any(char not in _NAME_CHARS for char in text):
        raise ParseError(
            f"Line {line_number}: {kind} name may contain only A-Z, a-z, 0-9, -, _, and /"
        )
    return text


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
        limit = _parse_integer_literal(text, line_number, f"{command} -n")
    except ValueError as exc:
        raise ParseError(f"Line {line_number}: {command} -n needs a non-negative integer") from exc

    if limit < 0:
        raise ParseError(f"Line {line_number}: {command} -n needs a non-negative integer")
    return limit


def _parse_integer_literal(text: str, line_number: int, context: str) -> int:
    if text == "true":
        return 1
    if text == "false":
        return 0
    try:
        return int(text)
    except ValueError as exc:
        raise ParseError(f"Line {line_number}: {context} needs an integer literal") from exc


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
    return BranchRef(_parse_name(token, tokens.line_number, "ref"))


def _validate_function_statement_starts(lines: list[_Line]) -> None:
    for line in lines:
        stripped = _strip_comment(line.text).strip()
        if not stripped or _is_comment(stripped) or _is_conflict_marker(stripped):
            continue
        if stripped.startswith("git ") or stripped == "git" or stripped == "exit":
            continue
        raise ParseError(f"Line {line.number}: Function body statements must start with git or be exit")


def _validate_function_parameter_uses(lines: list[_Line], parameter_kinds: dict[str, str]) -> None:
    for line in lines:
        raw = _strip_comment(line.text).strip()
        if not raw or _is_comment(raw):
            continue

        for name in _find_parameter_refs(raw):
            if name not in parameter_kinds:
                raise ParseError(f"Line {line.number}: Unknown parameter: {name}")

        if raw.startswith("<<<<<<<"):
            _require_parameter_kinds(raw[7:].strip(), parameter_kinds, _REF_PARAMETER_KINDS, line.number, "commit reference")
            continue
        if raw.startswith(">>>>>>>"):
            _require_parameter_kinds(raw[7:].strip(), parameter_kinds, _REF_PARAMETER_KINDS, line.number, "commit reference")
            continue
        if raw.startswith("=======") or raw == "exit":
            continue

        try:
            parts = shlex.split(raw, posix=True)
        except ValueError:
            continue

        if len(parts) < 2 or parts[0] != "git":
            continue

        command = parts[1]
        args = parts[2:]
        if command == "commit":
            _validate_commit_parameters(raw, args, parameter_kinds, line.number)
        elif command == "branch":
            _validate_branch_parameters(args, parameter_kinds, line.number)
        elif command == "checkout":
            _validate_checkout_parameters(args, parameter_kinds, line.number)
        elif command == "reset":
            if args:
                _require_parameter_kinds(args[0], parameter_kinds, _REF_PARAMETER_KINDS, line.number, "commit reference")
        elif command == "merge":
            _validate_merge_parameters(args, parameter_kinds, line.number)
        elif command == "cherry-pick":
            _validate_cherry_pick_parameters(args, parameter_kinds, line.number)
        elif command in {"revert", "rebase"}:
            if args:
                _require_parameter_kinds(args[0], parameter_kinds, _REF_PARAMETER_KINDS, line.number, "commit reference")
        elif command == "tag":
            _validate_tag_parameters(args, parameter_kinds, line.number)
        elif command in {"show", "log", "rev-list"}:
            _validate_list_like_parameters(args, parameter_kinds, line.number)


_REF_PARAMETER_KINDS = frozenset({"-r", "-l", "-b", "-p", "-t"})


def _validate_commit_parameters(raw: str, args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    message_is_quoted = _commit_message_is_quoted(raw)
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--amend":
            i += 1
        elif arg == "-m":
            if i + 1 < len(args):
                expected = {"-s"} if message_is_quoted else {"-i"}
                _require_parameter_kinds(args[i + 1], parameter_kinds, expected, line_number, "commit message")
            i += 2
        elif arg.startswith("-m="):
            expected = {"-s"} if message_is_quoted else {"-i"}
            _require_parameter_kinds(arg[3:], parameter_kinds, expected, line_number, "commit message")
            i += 1
        else:
            i += 1


def _validate_branch_parameters(args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    if not args:
        return
    if args[0] == "-d":
        for arg in args[1:]:
            _require_parameter_kinds(arg, parameter_kinds, {"-b"}, line_number, "branch deletion")
        return

    _require_parameter_kinds(args[0], parameter_kinds, {"-l"}, line_number, "new branch name")
    if len(args) > 1:
        _require_parameter_kinds(args[1], parameter_kinds, _REF_PARAMETER_KINDS, line_number, "commit reference")


def _validate_checkout_parameters(args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    if not args:
        return
    if args[0] == "-b":
        if len(args) > 1:
            _require_parameter_kinds(args[1], parameter_kinds, {"-l"}, line_number, "new branch name")
        if len(args) > 2:
            _require_parameter_kinds(args[2], parameter_kinds, _REF_PARAMETER_KINDS, line_number, "commit reference")
        return

    _require_parameter_kinds(args[0], parameter_kinds, {"-l", "-b", "-p"}, line_number, "branch name")


def _validate_merge_parameters(args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"--continue", "--abort"}:
            if i + 1 < len(args):
                _require_parameter_kinds(args[i + 1], parameter_kinds, {"-l"}, line_number, "merge label")
            return
        if arg == "-s":
            if i + 1 < len(args):
                _require_parameter_kinds(args[i + 1], parameter_kinds, {"-c"}, line_number, "merge condition")
            i += 2
        elif arg.startswith("-s="):
            _require_parameter_kinds(arg[3:], parameter_kinds, {"-c"}, line_number, "merge condition")
            i += 1
        else:
            _require_parameter_kinds(arg, parameter_kinds, {"-l"}, line_number, "merge label")
            i += 1


def _validate_cherry_pick_parameters(args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    if not args:
        return

    _require_parameter_kinds(args[0], parameter_kinds, _REF_PARAMETER_KINDS, line_number, "commit reference")
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "-s":
            if i + 1 < len(args):
                _require_parameter_kinds(args[i + 1], parameter_kinds, {"-o"}, line_number, "cherry-pick strategy")
            i += 2
        elif arg.startswith("-s="):
            _require_parameter_kinds(arg[3:], parameter_kinds, {"-o"}, line_number, "cherry-pick strategy")
            i += 1
        else:
            i += 1


def _validate_tag_parameters(args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    if not args:
        return
    if args[0] == "-d":
        for arg in args[1:]:
            _require_parameter_kinds(arg, parameter_kinds, {"-t"}, line_number, "tag deletion")
        return
    _require_parameter_kinds(args[0], parameter_kinds, {"-l"}, line_number, "new tag name")


def _validate_list_like_parameters(args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-n":
            if i + 1 < len(args):
                _require_parameter_kinds(args[i + 1], parameter_kinds, {"-i"}, line_number, "list limit")
            i += 2
        elif arg.startswith("-n="):
            _require_parameter_kinds(arg[3:], parameter_kinds, {"-i"}, line_number, "list limit")
            i += 1
        elif arg == "--reverse":
            i += 1
        else:
            _require_parameter_kinds(arg, parameter_kinds, _REF_PARAMETER_KINDS, line_number, "commit reference")
            i += 1


def _require_parameter_kinds(
        text: str,
        parameter_kinds: dict[str, str],
        expected: set[str] | frozenset[str],
        line_number: int,
        context: str,
) -> None:
    for name in _find_parameter_refs(text):
        actual = parameter_kinds[name]
        if actual not in expected:
            expected_text = ", ".join(sorted(expected))
            raise ParseError(
                f"Line {line_number}: Parameter {name} has type {actual}, "
                f"but {context} expects {expected_text}"
            )


def _substitute_function_parameter_placeholders(body: str, parameter_kinds: dict[str, str]) -> str:
    placeholders = {
        "-i": "1",
        "-s": "text",
        "-l": "new-label",
        "-b": "existing-branch",
        "-p": "protected-branch",
        "-t": "existing-tag",
        "-r": "HEAD",
        "-c": "==",
        "-o": "+",
    }

    def replace(match):
        return placeholders[parameter_kinds[match.group(1)]]

    return re.sub(r"\$([A-Za-z0-9_/-]+)", replace, body)


def _find_parameter_refs(text: str) -> list[str]:
    return re.findall(r"\$([A-Za-z0-9_/-]+)", text)


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
    in_single_quote = False
    in_quote = False
    escaped = False
    for i, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "'" and not in_quote:
            in_single_quote = not in_single_quote
            continue
        if char == '"' and not in_single_quote:
            in_quote = not in_quote
            continue
        if char == "#" and not in_quote and not in_single_quote:
            return text[:i]
    return text


def _split_statement_separators(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    i = 0
    in_single_quote = False
    in_double_quote = False
    escaped = False

    while i < len(text):
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
        if text.startswith("&&", i) and not in_single_quote and not in_double_quote:
            part = text[start:i].strip()
            if part:
                parts.append(part)
            i += 2
            start = i
            continue
        i += 1

    part = text[start:].strip()
    if part:
        parts.append(part)
    return parts


def _is_multiline_alias_start(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("git config alias.") and _has_unclosed_single_quote(text)


def _is_triple_commit_string_start(text: str) -> bool:
    return _triple_commit_string_start(text) is not None


def _has_unclosed_triple_quote(text: str) -> bool:
    return text.count('"""') % 2 == 1


def _triple_commit_string_start(text: str) -> int | None:
    message_start = _commit_message_start(text)
    if message_start is None:
        return None
    if text.startswith('"""', message_start):
        return message_start
    return None


def _has_unclosed_single_quote(text: str) -> bool:
    in_single_quote = False
    in_double_quote = False
    escaped = False

    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
    return in_single_quote


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


def _is_conflict_marker(stripped: str) -> bool:
    return stripped.startswith(("<<<<<<<", "=======", ">>>>>>>"))


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
