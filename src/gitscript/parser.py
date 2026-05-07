import shlex
import re
from dataclasses import dataclass
from typing import Iterable

from gitscript.commit_range import CommitRange, CommitSelector, SymmetricDifferenceRange
from gitscript.lexer import (
    LexError,
    Token,
    TokenKind,
    has_unclosed_single_quote as lexer_has_unclosed_single_quote,
    is_identifier_text,
    lex_statement,
    strip_comment,
)
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
    Init,
    ListTags,
    Pull,
    Push,
    Rebase,
    Revert,
    RevertRange,
    Reset,
    RevList,
    RevListRange,
    Rescue,
    Show,
    Statement,
    StatementBlock,
    Sequence,
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

        if _has_unclosed_single_quote(_strip_comment(text)):
            collected = [text]
            while _has_unclosed_single_quote(_strip_comment("\n".join(collected))):
                i += 1
                if i >= len(raw_lines):
                    message = f"Line {line_number}: single-quoted block is missing closing quote"
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
            _validate_conflict_marker_line(text, line_number)
            stripped = text.strip()
            if stripped:
                lines.append(_Line(line_number, stripped))

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
    statements = parse(_substitute_function_parameter_placeholders(body, parameter_kinds))
    _validate_function_has_no_alias_definitions(statements)


def _validate_function_has_no_alias_definitions(statements: list[Statement]) -> None:
    if any(_statement_contains_alias_definition(statement) for statement in statements):
        raise ParseError("Function bodies cannot define aliases")


def _statement_contains_alias_definition(statement: Statement) -> bool:
    if isinstance(statement, (DefineAlias, DefineFunction)):
        return True
    if isinstance(statement, (Sequence, Rescue)):
        return _statement_contains_alias_definition(statement.left) or _statement_contains_alias_definition(statement.right)
    if isinstance(statement, StatementBlock):
        return any(_statement_contains_alias_definition(nested) for nested in statement.statements)
    if isinstance(statement, Conflict):
        return any(_statement_contains_alias_definition(nested) for nested in statement.block_a + statement.block_b)
    return False


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

    def _parse_block(self, stop_markers: tuple[TokenKind, ...] = ()) -> list[Statement]:
        statements: list[Statement] = []

        while (line := self._current()) is not None:
            first_kind = _first_token_kind(line.text, line.number)
            if first_kind is None:
                self.index += 1
                continue

            if first_kind in stop_markers:
                break

            if first_kind == TokenKind.CONFLICT_START:
                raise self._error(line, "Conflict block must be preceded by git merge")

            if first_kind in {TokenKind.CONFLICT_MIDDLE, TokenKind.CONFLICT_END}:
                break

            statement = _parse_statement(line)
            self.index += 1
            statements.append(self._resolve_merge_starts(statement, line))

        return statements

    def _resolve_merge_starts(self, statement: Statement | _MergeStart, line: _Line) -> Statement:
        if isinstance(statement, _MergeStart):
            self._skip_ignored_lines()
            conflict_start = self._current()
            if conflict_start is None:
                if self.allow_incomplete:
                    raise IncompleteInput(f"Line {line.number}: git merge needs a conflict block")
                raise self._error(line, "git merge needs a conflict block")
            if not _line_starts_with(conflict_start.text, conflict_start.number, {TokenKind.CONFLICT_START}):
                raise self._error(conflict_start, "git merge must be followed by a conflict block")
            return self._parse_conflict(conflict_start, statement.condition, statement.label)
        if isinstance(statement, Sequence):
            statement.left = self._resolve_merge_starts(statement.left, line)
            statement.right = self._resolve_merge_starts(statement.right, line)
            return statement
        if isinstance(statement, Rescue):
            statement.left = self._resolve_merge_starts(statement.left, line)
            statement.right = self._resolve_merge_starts(statement.right, line)
            return statement
        return statement

    def _parse_conflict(self, start: _Line, condition: Condition, label: str | None) -> Conflict:
        ref_a = _parse_conflict_marker_ref(start, TokenKind.CONFLICT_START, "Conflict start marker")

        self.index += 1
        block_a = self._parse_block((TokenKind.CONFLICT_MIDDLE,))

        middle = self._current()
        if middle is None or not _line_starts_with(middle.text, middle.number, {TokenKind.CONFLICT_MIDDLE}):
            if self.allow_incomplete and middle is None:
                raise IncompleteInput(f"Line {start.number}: Conflict block is missing =======")
            raise self._error(start, "Conflict block is missing =======")

        self.index += 1
        block_b = self._parse_block((TokenKind.CONFLICT_END,))

        end = self._current()
        if end is None or not _line_starts_with(end.text, end.number, {TokenKind.CONFLICT_END}):
            if self.allow_incomplete and end is None:
                raise IncompleteInput(f"Line {start.number}: Conflict block is missing >>>>>>>")
            raise self._error(start, "Conflict block is missing >>>>>>>")

        ref_b = _parse_conflict_marker_ref(end, TokenKind.CONFLICT_END, "Conflict end marker")

        self.index += 1
        return Conflict(
            ref_a,
            ref_b,
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
            if _first_token_kind(line.text, line.number) is not None:
                return
            self.index += 1

    @staticmethod
    def _error(line: _Line, message: str) -> ParseError:
        return ParseError(f"Line {line.number}: {message}")


def _lex_statement(text: str, line_number: int) -> list[Token]:
    try:
        return lex_statement(text, line_number)
    except LexError as exc:
        raise ParseError(str(exc)) from exc


def _token_values(tokens: list[Token]) -> list[str]:
    return [token.value for token in _argument_tokens(tokens)]


def _argument_tokens(tokens: list[Token]) -> list[Token]:
    arguments: list[Token] = []
    i = 0
    while i < len(tokens):
        group = tokens[i].group
        grouped = [tokens[i]]
        i += 1
        while i < len(tokens) and tokens[i].group == group:
            grouped.append(tokens[i])
            i += 1

        if len(grouped) == 1:
            arguments.append(grouped[0])
            continue

        quoted = next((token for token in grouped if token.quoted), None)
        arguments.append(
            Token(
                grouped[0].kind,
                "".join(token.value for token in grouped),
                grouped[0].line,
                grouped[0].column,
                quoted is not None,
                quoted.quote if quoted is not None else None,
                group,
            )
        )
    return arguments


def _combine_tokens(tokens: list[Token]) -> Token:
    if len(tokens) == 1:
        return tokens[0]

    quoted = next((token for token in tokens if token.quoted), None)
    return Token(
        tokens[0].kind,
        "".join(token.value for token in tokens),
        tokens[0].line,
        tokens[0].column,
        quoted is not None,
        quoted.quote if quoted is not None else None,
        tokens[0].group,
    )


class _TokenCursor:
    def __init__(self, tokens: list[Token], line_number: int):
        self.tokens = tokens
        self.line_number = line_number
        self.index = 0

    @property
    def done(self) -> bool:
        return self.index >= len(self.tokens)

    def peek(self) -> Token | None:
        if self.done:
            return None
        return self.tokens[self.index]

    def next(self) -> Token | None:
        token = self.peek()
        if token is not None:
            self.index += 1
        return token

    def accept(self, kind: TokenKind, value: str | None = None) -> Token | None:
        token = self.peek()
        if token is None or token.kind != kind:
            return None
        if value is not None and token.value != value:
            return None
        self.index += 1
        return token

    def expect(self, kind: TokenKind, context: str, value: str | None = None) -> Token:
        token = self.accept(kind, value)
        if token is not None:
            return token
        expected = value if value is not None else _token_kind_name(kind)
        raise ParseError(f"Line {self.line_number}: {context} expects {expected}")

    def expect_any(self, kinds: set[TokenKind] | frozenset[TokenKind], context: str) -> Token:
        token = self.peek()
        if token is not None and token.kind in kinds:
            self.index += 1
            return token
        expected = " or ".join(_token_kind_name(kind) for kind in sorted(kinds, key=lambda item: item.name))
        raise ParseError(f"Line {self.line_number}: {context} expects {expected}")

    def rest(self) -> list[Token]:
        rest = self.tokens[self.index:]
        self.index = len(self.tokens)
        return rest

    def expect_done(self, command: str) -> None:
        if not self.done:
            raise ParseError(f"Line {self.line_number}: Unexpected {command} argument: {self.peek().value}")

    def consume_argument(self, context: str) -> Token:
        token = self.peek()
        if token is None:
            raise ParseError(f"Line {self.line_number}: {context} needs an argument")

        group = token.group
        grouped: list[Token] = []
        while self.peek() is not None and self.peek().group == group:
            grouped.append(self.next())
        return _combine_tokens(grouped)

    def remaining_arguments(self) -> list[Token]:
        args = _argument_tokens(self.tokens[self.index:])
        self.index = len(self.tokens)
        return args


def _token_kind_name(kind: TokenKind) -> str:
    return kind.name.lower().replace("_", " ")


_COMMANDS = {
    TokenKind.COMMIT,
    TokenKind.BRANCH,
    TokenKind.CHECKOUT,
    TokenKind.CONFIG,
    TokenKind.RESET,
    TokenKind.MERGE,
    TokenKind.CHERRY_PICK,
    TokenKind.REVERT,
    TokenKind.REBASE,
    TokenKind.TAG,
    TokenKind.SHOW,
    TokenKind.LOG,
    TokenKind.REV_LIST,
    TokenKind.INIT,
    TokenKind.CLONE,
    TokenKind.PULL,
    TokenKind.PUSH,
}

_PARAMETER_TYPE_OPTIONS = frozenset({"-i", "-s", "-l", "-b", "-p", "-t", "-c", "-m", "-o"})

_OPERATOR_BY_KIND = {
    TokenKind.STRATEGY_OURS: Operator.OURS,
    TokenKind.STRATEGY_THEIRS: Operator.THEIRS,
    TokenKind.STRATEGY_MIN: Operator.MIN,
    TokenKind.STRATEGY_MAX: Operator.MAX,
    TokenKind.STRATEGY_ADD: Operator.ADD,
    TokenKind.STRATEGY_SUBTRACT: Operator.SUBTRACT,
    TokenKind.STRATEGY_MULTIPLY: Operator.MULTIPLY,
    TokenKind.STRATEGY_DIVIDE: Operator.DIVIDE,
    TokenKind.STRATEGY_MODULO: Operator.MODULO,
    TokenKind.STRATEGY_GT: Operator.GT,
    TokenKind.STRATEGY_LT: Operator.LT,
    TokenKind.STRATEGY_EQ: Operator.EQ,
    TokenKind.STRATEGY_NEQ: Operator.NEQ,
    TokenKind.STRATEGY_GTE: Operator.GTE,
    TokenKind.STRATEGY_LTE: Operator.LTE,
}

_CONDITION_BY_KIND = {
    TokenKind.STRATEGY_GT: Condition.GT,
    TokenKind.STRATEGY_LT: Condition.LT,
    TokenKind.STRATEGY_EQ: Condition.EQ,
    TokenKind.STRATEGY_NEQ: Condition.NEQ,
    TokenKind.STRATEGY_GTE: Condition.GTE,
    TokenKind.STRATEGY_LTE: Condition.LTE,
    TokenKind.CONDITION_IS: Condition.IS,
}

_CONFLICT_MARKER_KINDS = frozenset({
    TokenKind.CONFLICT_START,
    TokenKind.CONFLICT_MIDDLE,
    TokenKind.CONFLICT_END,
})


def _first_token_kind(text: str, line_number: int) -> TokenKind | None:
    tokens = _lex_statement(_strip_comment(text).strip(), line_number)
    if not tokens:
        return None
    return tokens[0].kind


def _line_starts_with(text: str, line_number: int, kinds: set[TokenKind] | frozenset[TokenKind]) -> bool:
    first_kind = _first_token_kind(text, line_number)
    return first_kind in kinds if first_kind is not None else False


def _validate_conflict_marker_line(text: str, line_number: int) -> None:
    tokens = _lex_statement(_strip_comment(text).strip(), line_number)
    if not any(token.kind in _CONFLICT_MARKER_KINDS for token in tokens):
        return
    if any(token.kind in {TokenKind.AND, TokenKind.OR} for token in tokens):
        raise ParseError(f"Line {line_number}: Conflict markers cannot share a line with && or ||")


def _parse_statement(line: _Line) -> Statement | _MergeStart:
    raw = _strip_comment(line.text).strip()
    tokens = _lex_statement(raw, line.number)
    return _parse_statement_expression(tokens, line.number)


def _parse_statement_expression(tokens: list[Token], line_number: int) -> Statement | _MergeStart:
    return _parse_rescue_expression(tokens, line_number)


def _parse_rescue_expression(tokens: list[Token], line_number: int) -> Statement | _MergeStart:
    parts = _split_tokens(tokens, TokenKind.OR)
    statement = _parse_sequence_expression(parts[0], line_number)
    for part in parts[1:]:
        right = _parse_sequence_expression(part, line_number)
        statement = Rescue(statement, right)
    return statement


def _parse_sequence_expression(tokens: list[Token], line_number: int) -> Statement | _MergeStart:
    parts = _split_tokens(tokens, TokenKind.AND)
    statement = _parse_statement_atom(parts[0], line_number)
    for part in parts[1:]:
        right = _parse_statement_atom(part, line_number)
        statement = Sequence(statement, right)
    return statement


def _parse_statement_atom(tokens: list[Token], line_number: int) -> Statement | _MergeStart:
    if len(tokens) == 1 and tokens[0].kind == TokenKind.STRING_LITERAL and tokens[0].value.startswith("!"):
        return StatementBlock(parse(tokens[0].value[1:]))
    return _parse_simple_statement(tokens, line_number)


def _split_tokens(tokens: list[Token], separator: TokenKind) -> list[list[Token]]:
    parts: list[list[Token]] = []
    current: list[Token] = []
    for token in tokens:
        if token.kind == separator:
            if not current:
                raise ParseError(f"Line {token.line}: Missing statement before {token.value}")
            parts.append(current)
            current = []
        else:
            current.append(token)
    if not current:
        raise ParseError(f"Line {tokens[-1].line if tokens else 0}: Missing statement after separator")
    parts.append(current)
    return parts


def _parse_simple_statement(tokens: list[Token], line_number: int) -> Statement | _MergeStart:
    if len(tokens) == 1 and tokens[0].kind == TokenKind.EXIT:
        return Exit()

    stream = _TokenCursor(tokens, line_number)
    if not stream.accept(TokenKind.GIT):
        raise ParseError(f"Line {line_number}: Expected a git command")
    command = stream.expect_any(_COMMANDS | {TokenKind.IDENTIFIER}, "git command")

    if command.kind == TokenKind.INIT:
        stream.expect_done("git init")
        return Init()
    if command.kind == TokenKind.CLONE:
        raise ParseError(f"Line {line_number}: git clone must be expanded before parsing")
    if command.kind == TokenKind.PULL:
        return _parse_pull(stream)
    if command.kind == TokenKind.PUSH:
        return _parse_push(stream)
    if command.kind == TokenKind.COMMIT:
        return _parse_commit(stream)
    if command.kind == TokenKind.BRANCH:
        return _parse_branch(stream)
    if command.kind == TokenKind.CHECKOUT:
        return _parse_checkout(stream)
    if command.kind == TokenKind.CONFIG:
        return _parse_config(stream)
    if command.kind == TokenKind.RESET:
        ref = _parse_required_ref_argument(stream, "git reset")
        stream.expect_done("git reset")
        return Reset(ref)
    if command.kind == TokenKind.MERGE:
        return _parse_merge(stream)
    if command.kind == TokenKind.CHERRY_PICK:
        return _parse_cherry_pick(stream)
    if command.kind == TokenKind.REVERT:
        selectors = _parse_required_commit_selectors(stream, "git revert")
        if len(selectors) == 1 and not isinstance(selectors[0], (CommitRange, SymmetricDifferenceRange)):
            return Revert(selectors[0])
        return RevertRange(selectors)
    if command.kind == TokenKind.REBASE:
        ref = _parse_required_ref_argument(stream, "git rebase")
        stream.expect_done("git rebase")
        return Rebase(ref)
    if command.kind == TokenKind.TAG:
        return _parse_tag(stream)
    if command.kind == TokenKind.SHOW:
        ref = _parse_optional_ref_argument(stream)
        stream.expect_done("git show")
        return Show(ref if ref is not None else HeadRef())
    if command.kind == TokenKind.LOG:
        selectors, limit, reverse, oneline, graph, include_all = _parse_list_args(
            stream,
            "git log",
            allow_oneline=True,
            allow_graph=True,
            allow_all=True,
        )
        if len(selectors) == 1 and not isinstance(selectors[0], (CommitRange, SymmetricDifferenceRange)):
            return Log(selectors[0], limit, reverse, oneline, graph, include_all)
        return LogRange(selectors, limit, reverse, oneline, graph, include_all)
    if command.kind == TokenKind.REV_LIST:
        selectors, limit, reverse, _, _, include_all = _parse_list_args(stream, "git rev-list", allow_all=True)
        if len(selectors) == 1 and not isinstance(selectors[0], (CommitRange, SymmetricDifferenceRange)):
            return RevList(selectors[0], limit, reverse, include_all)
        return RevListRange(selectors, limit, reverse, include_all)

    return AliasCall(command.value, _token_values(stream.rest()))


def _parse_branch(stream: _TokenCursor) -> Statement:
    if stream.done:
        return ListBranches()

    if stream.accept(TokenKind.OPTION, "-d"):
        names = []
        while not stream.done:
            names.append(_parse_name_token(stream.expect(TokenKind.IDENTIFIER, "git branch -d"), "branch"))
        if not names:
            raise ParseError(f"Line {stream.line_number}: git branch -d needs at least one branch name")
        return DeleteBranches(names)

    name = _parse_name_token(stream.expect(TokenKind.IDENTIFIER, "git branch"), "branch")
    ref = _parse_optional_ref_argument(stream)
    stream.expect_done("git branch")
    return Branch(name, ref if ref is not None else HeadRef())


def _parse_checkout(stream: _TokenCursor) -> Statement:
    if stream.accept(TokenKind.OPTION, "-b"):
        name = _parse_name_token(stream.expect(TokenKind.IDENTIFIER, "git checkout -b"), "branch")
        ref = _parse_optional_ref_argument(stream)
        stream.expect_done("git checkout")
        return Checkout(name, ref if ref is not None else HeadRef())

    name = _parse_name_token(stream.expect(TokenKind.IDENTIFIER, "git checkout"), "branch")
    stream.expect_done("git checkout")
    return Checkout(name)


def _parse_tag(stream: _TokenCursor) -> Statement:
    if stream.done:
        return ListTags()

    if stream.accept(TokenKind.OPTION, "-d"):
        names = []
        while not stream.done:
            names.append(_parse_name_token(stream.expect(TokenKind.IDENTIFIER, "git tag -d"), "tag"))
        if not names:
            raise ParseError(f"Line {stream.line_number}: git tag -d needs at least one tag name")
        return DeleteTags(names)

    name = _parse_name_token(stream.expect(TokenKind.IDENTIFIER, "git tag"), "tag")
    ref = _parse_optional_ref_argument(stream)
    stream.expect_done("git tag")
    return Tag(name, ref if ref is not None else HeadRef())


def _parse_config(stream: _TokenCursor) -> Statement:
    key = stream.expect(TokenKind.CONFIG_KEY, "git config")
    if key.value.startswith("alias."):
        return _parse_alias_config(key, stream)

    if key.value == "commit.verbose":
        value = stream.expect(TokenKind.INT_LITERAL, "git config value")
        stream.expect_done("git config")
        return Config(key.value, _parse_integer_literal(value.value, stream.line_number, "commit.verbose"))

    if key.value == "merge.verbosity":
        value = stream.expect(TokenKind.INT_LITERAL, "git config value")
        stream.expect_done("git config")
        verbosity = _parse_integer_literal(value.value, stream.line_number, "merge.verbosity")
        if verbosity not in {0, 1, 2}:
            raise ParseError(f"Line {stream.line_number}: merge.verbosity must be 0, 1, or 2")
        return Config(key.value, verbosity)

    if key.value == "core.worktree":
        value = stream.consume_argument("git config core.worktree").value
        stream.expect_done("git config core.worktree")
        return Config(key.value, value)

    raise ParseError(f"Line {stream.line_number}: Unknown config key: {key.value}")


def _parse_pull(stream: _TokenCursor) -> Pull:
    file_path = stream.consume_argument("git pull").value
    aliases: list[tuple[str, str]] = []
    while not stream.done:
        alias = stream.consume_argument("git pull alias").value
        if ":" in alias:
            target, source = alias.split(":", 1)
            aliases.append((
                _parse_name(target, stream.line_number, "alias"),
                _parse_name(source, stream.line_number, "alias"),
            ))
        else:
            aliases.append((_parse_name(alias, stream.line_number, "alias"), _parse_name(alias, stream.line_number, "alias")))
    return Pull(file_path, aliases)


def _parse_push(stream: _TokenCursor) -> Push:
    aliases = []
    while not stream.done:
        aliases.append(_parse_name_token(stream.expect(TokenKind.IDENTIFIER, "git push alias"), "alias"))
    return Push(aliases)


def _parse_alias_config(key: Token, stream: _TokenCursor) -> DefineAlias | DefineFunction:
    name = key.value[len("alias."):]
    _parse_name(name, stream.line_number, "alias")
    args = stream.remaining_arguments()

    if len(args) < 1:
        raise ParseError(f"Line {stream.line_number}: git config alias needs a value")

    parameters: list[Parameter] = []
    i = 0
    while i < len(args) - 1:
        kind = args[i]
        if kind.kind != TokenKind.OPTION or kind.value not in _PARAMETER_TYPE_OPTIONS:
            raise ParseError(f"Line {stream.line_number}: Unknown function parameter type: {kind.value}")
        parameter = args[i + 1]
        parameter_name, default = _parse_parameter(parameter, kind.value, stream.line_number)
        parameters.append(Parameter(kind.value, parameter_name, default))
        i += 2

    if i != len(args) - 1:
        raise ParseError(f"Line {stream.line_number}: Function parameter needs a name")

    value = args[-1].value
    if value.startswith("!"):
        return DefineFunction(name, parameters, value[1:])

    if parameters:
        raise ParseError(f"Line {stream.line_number}: Shortform aliases cannot declare parameters")
    return DefineAlias(name, value)


def _parse_parameter(token: Token, kind: str, line_number: int) -> tuple[str, str | None]:
    if "=" in token.value:
        name_text, default = token.value.split("=", 1)
    else:
        name_text = token.value
        default = None

    parts = _lex_statement(name_text, line_number)
    cursor = _TokenCursor(parts, line_number)
    name = _parse_name_token(cursor.expect(TokenKind.IDENTIFIER, "function parameter"), "parameter")
    if kind in {"-l", "-b", "-p", "-t"} and name == "main":
        raise ParseError(f"Line {line_number}: {kind} parameter cannot be named main")
    cursor.expect_done("function parameter")

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
    if kind == "-c":
        _parse_ref(value, line_number)
        return value
    if kind == "-m":
        _parse_condition(value, line_number)
        return value
    if kind == "-o":
        _parse_operator(value, line_number)
        return value
    raise ParseError(f"Line {line_number}: Unknown function parameter type: {kind}")


def _parse_commit(stream: _TokenCursor) -> Statement:
    amend = False
    string_mode = False
    value: str | None = None

    while not stream.done:
        if stream.accept(TokenKind.OPTION, "--amend"):
            amend = True
            continue

        if stream.accept(TokenKind.OPTION, "-m"):
            if string_mode or value is not None:
                raise ParseError(f"Line {stream.line_number}: git commit accepts only one value")
            string_mode = True
            if stream.accept(TokenKind.EQUALS):
                if stream.done:
                    value = ""
                else:
                    value = stream.consume_argument("git commit -m").value
            else:
                if not stream.done:
                    value = stream.consume_argument("git commit -m").value
            continue

        if stream.peek().kind == TokenKind.OPTION:
            raise ParseError(f"Line {stream.line_number}: Unexpected git commit argument: {stream.peek().value}")

        if value is not None or string_mode:
            raise ParseError(f"Line {stream.line_number}: git commit accepts only one value")
        value = stream.consume_argument("git commit").value

    if string_mode:
        if amend:
            raise ParseError(f"Line {stream.line_number}: --amend is not allowed for string commits")
        return CommitString(value)

    if value is None:
        return Commit(None, amend)

    return Commit(_parse_integer_literal(value, stream.line_number, "git commit"), amend)


def _parse_cherry_pick(stream: _TokenCursor) -> CherryPick | CherryPickRange:
    selectors: list[CommitSelector] = []
    op = Operator.THEIRS
    while not stream.done:
        if stream.accept(TokenKind.OPTION, "-s"):
            stream.accept(TokenKind.EQUALS)
            token = stream.peek()
            if token is None:
                raise ParseError(f"Line {stream.line_number}: git cherry-pick -s needs a strategy")
            if token.kind not in _OPERATOR_BY_KIND:
                raise ParseError(f"Line {token.line}: Unknown strategy: {token.value}")
            op = _parse_operator_token(stream.next())
            continue
        if stream.peek().kind == TokenKind.OPTION:
            raise ParseError(f"Line {stream.line_number}: Unexpected git cherry-pick argument: {stream.peek().value}")
        selectors.append(_parse_commit_selector(stream.consume_argument("git cherry-pick").value, stream.line_number))

    if not selectors:
        raise ParseError(f"Line {stream.line_number}: git cherry-pick needs at least one commit selector")

    if len(selectors) == 1 and not isinstance(selectors[0], (CommitRange, SymmetricDifferenceRange)):
        return CherryPick(selectors[0], op)
    return CherryPickRange(selectors, op)


def _parse_merge(stream: _TokenCursor) -> Statement | _MergeStart:
    condition = Condition.EQ
    label = None

    if stream.accept(TokenKind.OPTION, "--continue"):
        label = _parse_optional_label_argument(stream, "git merge --continue")
        stream.expect_done("git merge --continue")
        return MergeContinue(label)

    if stream.accept(TokenKind.OPTION, "--abort"):
        label = _parse_optional_label_argument(stream, "git merge --abort")
        stream.expect_done("git merge --abort")
        return MergeAbort(label)

    while not stream.done:
        if stream.accept(TokenKind.OPTION, "-s"):
            stream.accept(TokenKind.EQUALS)
            token = stream.peek()
            if token is None:
                raise ParseError(f"Line {stream.line_number}: git merge -s needs a condition")
            if token.kind not in _CONDITION_BY_KIND:
                raise ParseError(f"Line {token.line}: Unknown merge condition: {token.value}")
            condition = _parse_condition_token(stream.next())
            continue

        if stream.peek().kind == TokenKind.OPTION:
            raise ParseError(f"Line {stream.line_number}: Unexpected git merge argument: {stream.peek().value}")

        if label is not None:
            raise ParseError(f"Line {stream.line_number}: git merge accepts only one label")
        label = _parse_merge_label(stream.consume_argument("git merge label"))

    return _MergeStart(condition, label)


def _parse_optional_label_argument(stream: _TokenCursor, command: str) -> str | None:
    if stream.done:
        return None
    if stream.peek().kind == TokenKind.OPTION:
        raise ParseError(f"Line {stream.line_number}: Unexpected {command} argument: {stream.peek().value}")
    return _parse_merge_label(stream.consume_argument(command))


def _parse_operator(text: str, line_number: int) -> Operator:
    tokens = _lex_statement(text, line_number)
    if len(tokens) == 1 and tokens[0].kind in _OPERATOR_BY_KIND:
        return _parse_operator_token(tokens[0])
    raise ParseError(f"Line {line_number}: Unknown strategy: {text}")


def _parse_operator_token(token: Token) -> Operator:
    try:
        return _OPERATOR_BY_KIND[token.kind]
    except KeyError as exc:
        raise ParseError(f"Line {token.line}: Unknown strategy: {token.value}") from exc


def _parse_condition(text: str, line_number: int) -> Condition:
    tokens = _lex_statement(text, line_number)
    if len(tokens) == 1 and tokens[0].kind in _CONDITION_BY_KIND:
        return _parse_condition_token(tokens[0])
    raise ParseError(f"Line {line_number}: Unknown merge condition: {text}")


def _parse_condition_token(token: Token) -> Condition:
    try:
        return _CONDITION_BY_KIND[token.kind]
    except KeyError as exc:
        raise ParseError(f"Line {token.line}: Unknown merge condition: {token.value}") from exc


def _parse_name(text: str, line_number: int, kind: str) -> str:
    if text == "HEAD":
        raise ParseError(f"Line {line_number}: {kind} name cannot be HEAD")
    if text.startswith("-"):
        raise ParseError(f"Line {line_number}: {kind} name cannot start with -")
    if any(char not in _NAME_CHARS for char in text):
        raise ParseError(
            f"Line {line_number}: {kind} name may contain only A-Z, a-z, 0-9, -, _, and /"
        )
    if not is_identifier_text(text):
        raise ParseError(f"Line {line_number}: {kind} name cannot be a keyword or operator")
    return text


def _parse_name_token(token: Token, kind: str) -> str:
    if token.kind != TokenKind.IDENTIFIER:
        raise ParseError(f"Line {token.line}: {kind} name expects identifier")
    return _parse_name(token.value, token.line, kind)


def _parse_merge_label(token: Token) -> str:
    if token.kind in _OPERATOR_BY_KIND or token.kind in _CONDITION_BY_KIND:
        raise ParseError(f"Line {token.line}: merge label name cannot be an operator")
    if token.kind in {TokenKind.OPTION, TokenKind.EQUALS, TokenKind.TILDE, TokenKind.CARET, TokenKind.RANGE, TokenKind.SYMDIFF_RANGE}:
        raise ParseError(f"Line {token.line}: merge label name expects identifier")
    if token.value == "HEAD":
        raise ParseError(f"Line {token.line}: merge label name cannot be HEAD")
    if token.value.startswith("-"):
        raise ParseError(f"Line {token.line}: merge label name cannot start with -")
    if any(char not in _NAME_CHARS for char in token.value):
        raise ParseError(
            f"Line {token.line}: merge label name may contain only A-Z, a-z, 0-9, -, _, and /"
        )
    return token.value


def _parse_commit_selector(text: str, line_number: int) -> CommitSelector:
    tokens = _tokenize_ref(text, line_number)
    stream = _TokenCursor(tokens, line_number)
    left = _parse_ref_expr(stream)
    if stream.accept(TokenKind.SYMDIFF_RANGE):
        right = _parse_ref_expr(stream)
        stream.expect_done("symmetric difference range")
        return SymmetricDifferenceRange(left, right)
    if stream.accept(TokenKind.RANGE):
        right = _parse_ref_expr(stream)
        stream.expect_done("commit range")
        return CommitRange(left, right)
    stream.expect_done("commit reference")
    return left


def _parse_range_or_ref(text: str, line_number: int) -> Ref | CommitRange:
    selector = _parse_commit_selector(text, line_number)
    if isinstance(selector, SymmetricDifferenceRange):
        raise ParseError(f"Line {line_number}: Symmetric difference range is not valid here")
    return selector


def _parse_required_ref_argument(stream: _TokenCursor, command: str) -> Ref:
    token = stream.consume_argument(command)
    return _parse_ref(token.value, stream.line_number)


def _parse_optional_ref_argument(stream: _TokenCursor) -> Ref | None:
    if stream.done:
        return None
    return _parse_required_ref_argument(stream, "commit reference")


def _parse_required_range_or_ref_argument(stream: _TokenCursor, command: str) -> Ref | CommitRange:
    token = stream.consume_argument(command)
    return _parse_range_or_ref(token.value, stream.line_number)


def _parse_required_commit_selectors(stream: _TokenCursor, command: str) -> list[CommitSelector]:
    selectors: list[CommitSelector] = []
    while not stream.done:
        if stream.peek().kind == TokenKind.OPTION:
            raise ParseError(f"Line {stream.line_number}: Unexpected {command} argument: {stream.peek().value}")
        selectors.append(_parse_commit_selector(stream.consume_argument(command).value, stream.line_number))

    if not selectors:
        raise ParseError(f"Line {stream.line_number}: {command} needs at least one commit selector")
    return selectors


def _parse_list_args(
        stream: _TokenCursor,
        command: str,
        allow_oneline: bool = False,
        allow_graph: bool = False,
        allow_all: bool = False,
) -> tuple[list[CommitSelector], int | None, bool, bool, bool, bool]:
    limit = None
    reverse = False
    oneline = False
    graph = False
    include_all = False
    selectors: list[CommitSelector] = []

    while not stream.done:
        if stream.accept(TokenKind.OPTION, "--reverse"):
            reverse = True
            continue

        if stream.accept(TokenKind.OPTION, "--oneline"):
            if not allow_oneline:
                raise ParseError(f"Line {stream.line_number}: Unexpected {command} argument: --oneline")
            oneline = True
            continue

        if stream.accept(TokenKind.OPTION, "--graph"):
            if not allow_graph:
                raise ParseError(f"Line {stream.line_number}: Unexpected {command} argument: --graph")
            graph = True
            continue

        if stream.accept(TokenKind.OPTION, "--all"):
            if not allow_all:
                raise ParseError(f"Line {stream.line_number}: Unexpected {command} argument: --all")
            include_all = True
            continue

        if stream.accept(TokenKind.OPTION, "-n"):
            stream.accept(TokenKind.EQUALS)
            limit = _parse_limit_token(stream.expect(TokenKind.INT_LITERAL, f"{command} -n"), command)
            continue

        if stream.peek().kind == TokenKind.OPTION:
            raise ParseError(f"Line {stream.line_number}: Unexpected {command} argument: {stream.peek().value}")

        selectors.append(_parse_commit_selector(stream.consume_argument(command).value, stream.line_number))

    if not selectors:
        selectors.append(HeadRef())
    if graph and reverse:
        raise ParseError(f"Line {stream.line_number}: {command} --graph cannot be used with --reverse")
    if graph and oneline:
        raise ParseError(f"Line {stream.line_number}: {command} --graph cannot be used with --oneline")
    return selectors, limit, reverse, oneline, graph, include_all


def _parse_limit_token(token: Token, command: str) -> int:
    limit = _parse_integer_literal(token.value, token.line, f"{command} -n")
    if limit < 0:
        raise ParseError(f"Line {token.line}: {command} -n needs a non-negative integer")
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
    stream = _TokenCursor(_tokenize_ref(text, line_number), line_number)
    ref = _parse_ref_expr(stream)
    if not stream.done:
        raise ParseError(f"Line {line_number}: Unexpected token in commit reference: {stream.peek().value}")
    return ref


def _parse_conflict_marker_ref(line: _Line, marker: TokenKind, context: str) -> Ref:
    tokens = _lex_statement(_strip_comment(line.text).strip(), line.number)
    stream = _TokenCursor(tokens, line.number)
    stream.expect(marker, context)
    if stream.done:
        raise ParseError(f"Line {line.number}: {context} needs a commit reference")
    token = stream.consume_argument(context)
    stream.expect_done(context)
    return _parse_ref(token.value, line.number)


def _parse_ref_expr(stream: _TokenCursor) -> Ref:
    base = _parse_ref_atom(stream)
    while True:
        if stream.accept(TokenKind.CARET):
            base = ConstantOffsetRef(base, 1)
            continue
        if stream.accept(TokenKind.TILDE):
            if token := stream.accept(TokenKind.INT_LITERAL):
                offset_value = _parse_integer_literal(token.value, token.line, "commit reference offset")
                if offset_value < 0:
                    raise ParseError(f"Line {token.line}: Negative offsets are not valid syntax")
                base = ConstantOffsetRef(base, offset_value)
                continue
            return DynamicOffsetRef(base, _parse_ref_expr(stream))
        break
    return base


def _parse_ref_atom(stream: _TokenCursor) -> Ref:
    token = stream.next()
    if token is None:
        raise ParseError(f"Line {stream.line_number}: Expected commit reference")
    if token.kind == TokenKind.HEAD:
        return HeadRef()
    if token.kind == TokenKind.LPAREN:
        ref = _parse_ref_expr(stream)
        if not stream.accept(TokenKind.RPAREN):
            raise ParseError(f"Line {stream.line_number}: Missing ')' in commit reference")
        return ref
    if token.kind in {TokenKind.TILDE, TokenKind.CARET, TokenKind.RPAREN, TokenKind.RANGE, TokenKind.SYMDIFF_RANGE}:
        raise ParseError(f"Line {stream.line_number}: Expected commit reference before {token.value}")
    if token.kind == TokenKind.INT_LITERAL:
        raise ParseError(f"Line {stream.line_number}: Expected commit reference before integer literal")
    if token.kind == TokenKind.IDENTIFIER:
        return BranchRef(_parse_name(token.value, token.line, "ref"))
    raise ParseError(f"Line {stream.line_number}: Expected commit reference")


def _validate_function_statement_starts(lines: list[_Line]) -> None:
    for line in lines:
        tokens = _lex_statement(_strip_comment(line.text).strip(), line.number)
        if not tokens or tokens[0].kind in _CONFLICT_MARKER_KINDS:
            continue
        if tokens[0].kind in {TokenKind.GIT, TokenKind.EXIT}:
            continue
        if tokens[0].kind == TokenKind.STRING_LITERAL and tokens[0].value.startswith("!"):
            continue
        raise ParseError(f"Line {line.number}: Function body statements must start with git or be exit")


def _validate_function_parameter_uses(lines: list[_Line], parameter_kinds: dict[str, str]) -> None:
    for line in lines:
        raw = _strip_comment(line.text).strip()
        if not raw:
            continue

        try:
            tokens = _lex_statement(raw, line.number)
        except ParseError:
            continue

        if not tokens:
            continue

        if tokens[0].kind in {TokenKind.CONFLICT_START, TokenKind.CONFLICT_END}:
            marker_stream = _TokenCursor(tokens, line.number)
            marker_stream.next()
            if not marker_stream.done:
                _require_parameter_kinds(
                    marker_stream.consume_argument("commit reference").value,
                    parameter_kinds,
                    _REF_PARAMETER_KINDS,
                    line.number,
                    "commit reference",
                )
            continue
        if tokens[0].kind in {TokenKind.CONFLICT_MIDDLE, TokenKind.EXIT}:
            continue

        if len(tokens) < 2 or tokens[0].kind != TokenKind.GIT:
            continue

        command = tokens[1].kind
        args = _token_values(tokens[2:])
        if command == TokenKind.COMMIT:
            _validate_commit_parameters(raw, args, parameter_kinds, line.number)
        elif command == TokenKind.BRANCH:
            _validate_branch_parameters(args, parameter_kinds, line.number)
        elif command == TokenKind.CHECKOUT:
            _validate_checkout_parameters(args, parameter_kinds, line.number)
        elif command == TokenKind.RESET:
            if args:
                _require_parameter_kinds(args[0], parameter_kinds, _REF_PARAMETER_KINDS, line.number, "commit reference")
        elif command == TokenKind.MERGE:
            _validate_merge_parameters(args, parameter_kinds, line.number)
        elif command == TokenKind.CHERRY_PICK:
            _validate_cherry_pick_parameters(args, parameter_kinds, line.number)
        elif command in {TokenKind.REVERT, TokenKind.REBASE}:
            if args:
                _require_parameter_kinds(args[0], parameter_kinds, _REF_PARAMETER_KINDS, line.number, "commit reference")
        elif command == TokenKind.TAG:
            _validate_tag_parameters(args, parameter_kinds, line.number)
        elif command in {TokenKind.SHOW, TokenKind.LOG, TokenKind.REV_LIST}:
            _validate_list_like_parameters(args, parameter_kinds, line.number)


_REF_PARAMETER_KINDS = frozenset({"-c", "-l", "-b", "-p", "-t"})


def _validate_commit_parameters(raw: str, args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    del raw
    string_mode = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--amend":
            i += 1
        elif arg == "-m":
            string_mode = True
            if i + 1 < len(args):
                _require_parameter_kinds(args[i + 1], parameter_kinds, {"-s"}, line_number, "commit string")
            i += 2
        elif arg.startswith("-m="):
            string_mode = True
            _require_parameter_kinds(arg[3:], parameter_kinds, {"-s"}, line_number, "commit string")
            i += 1
        elif not arg.startswith("-") and not string_mode:
            _require_parameter_kinds(arg, parameter_kinds, {"-i"}, line_number, "integer commit")
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
                _require_parameter_kinds(args[i + 1], parameter_kinds, {"-m"}, line_number, "merge condition")
            i += 2
        elif arg.startswith("-s="):
            _require_parameter_kinds(arg[3:], parameter_kinds, {"-m"}, line_number, "merge condition")
            i += 1
        else:
            _require_parameter_kinds(arg, parameter_kinds, {"-l"}, line_number, "merge label")
            i += 1


def _validate_cherry_pick_parameters(args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    i = 0
    saw_selector = False
    while i < len(args):
        arg = args[i]
        if arg == "-s":
            if i + 1 < len(args):
                _require_parameter_kinds(args[i + 1], parameter_kinds, {"-o"}, line_number, "cherry-pick strategy")
            i += 2
        elif arg.startswith("-s="):
            _require_parameter_kinds(arg[3:], parameter_kinds, {"-o"}, line_number, "cherry-pick strategy")
            i += 1
        elif arg.startswith("-"):
            i += 1
        else:
            saw_selector = True
            _require_parameter_kinds(arg, parameter_kinds, _REF_PARAMETER_KINDS, line_number, "commit selector")
            i += 1
    if not saw_selector:
        return


def _validate_tag_parameters(args: list[str], parameter_kinds: dict[str, str], line_number: int) -> None:
    if not args:
        return
    if args[0] == "-d":
        for arg in args[1:]:
            _require_parameter_kinds(arg, parameter_kinds, {"-t"}, line_number, "tag deletion")
        return
    _require_parameter_kinds(args[0], parameter_kinds, {"-l"}, line_number, "new tag name")
    if len(args) > 1:
        _require_parameter_kinds(args[1], parameter_kinds, _REF_PARAMETER_KINDS, line_number, "commit reference")


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
        elif arg in {"--reverse", "--oneline", "--graph", "--all"}:
            i += 1
        else:
            _require_parameter_kinds(arg, parameter_kinds, _REF_PARAMETER_KINDS, line_number, "commit selector")
            i += 1


def _require_parameter_kinds(
        text: str,
        parameter_kinds: dict[str, str],
        expected: set[str] | frozenset[str],
        line_number: int,
        context: str,
) -> None:
    for name in _find_parameter_refs(text, parameter_kinds):
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
        "-c": "HEAD",
        "-m": "eq",
        "-o": "add",
    }

    replacements = {
        name: placeholders[kind]
        for name, kind in parameter_kinds.items()
    }
    return _substitute_parameter_names(body, replacements)


def _find_parameter_refs(text: str, parameter_kinds: dict[str, str]) -> list[str]:
    names = set(parameter_kinds)
    refs: list[str] = []
    for token in _lex_statement(text, 0):
        if token.kind == TokenKind.IDENTIFIER and token.value in names:
            refs.append(token.value)
    return refs


def _substitute_parameter_names(source: str, replacements: dict[str, str]) -> str:
    result: list[str] = []
    i = 0
    while i < len(source):
        if source.startswith('"""', i):
            end = source.find('"""', i + 3)
            if end == -1:
                result.append(source[i:])
                break
            result.append(source[i:end + 3])
            i = end + 3
            continue
        if source.startswith("'!", i):
            result.append("'!")
            i += 2
            continue
        if source[i] == "#":
            end = i
            while end < len(source) and source[end] not in "\r\n":
                end += 1
            result.append(source[i:end])
            i = end
            continue
        if source[i] in {"'", '"'}:
            quote = source[i]
            end = i + 1
            escaped = False
            while end < len(source):
                char = source[end]
                if quote == '"' and escaped:
                    escaped = False
                elif quote == '"' and char == "\\":
                    escaped = True
                elif char == quote:
                    end += 1
                    break
                end += 1
            result.append(source[i:end])
            i = end
            continue
        if source[i] in _NAME_CHARS:
            end = i + 1
            while end < len(source) and source[end] in _NAME_CHARS:
                end += 1
            name = source[i:end]
            result.append(replacements.get(name, name))
            i = end
            continue
        result.append(source[i])
        i += 1
    return "".join(result)


def _tokenize_ref(text: str, line_number: int) -> list[Token]:
    tokens = _lex_statement(text, line_number)
    if any(token.value.startswith("-") for token in tokens):
        raise ParseError(f"Line {line_number}: Negative offsets are not valid syntax")
    if not tokens:
        raise ParseError(f"Line {line_number}: Expected commit reference")
    return tokens


def _strip_comment(text: str) -> str:
    return strip_comment(text)


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
    return lexer_has_unclosed_single_quote(text)


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
