import sys
import re
import shlex
from dataclasses import dataclass
from typing import Optional

from gitscript.commit_range import CommitRange
from gitscript.refs import Ref, resolve, HeadRef
from gitscript.commands import commit, commit_string, branch, checkout, reset, show, log, tag, cherry_pick, \
    rebase, delete_branch, delete_tag, cherry_pick_range, revert, revert_range, log_range, rev_list, rev_list_range
from gitscript.operators import Condition, Operator
from gitscript.repo import Repo


class Statement:
    def run(self, repo: Repo):
        pass


class MergeContinueSignal(Exception):
    def __init__(self, label: Optional[str] = None):
        self.label = label


class MergeAbortSignal(Exception):
    def __init__(self, label: Optional[str] = None):
        self.label = label


class ExitSignal(Exception):
    pass


@dataclass
class AliasDefinition:
    fragment: str


@dataclass
class Parameter:
    kind: str
    name: str
    default: Optional[str] = None


@dataclass
class FunctionDefinition:
    parameters: list[Parameter]
    body: str

class Branch(Statement):
    def __init__(self, branch_name: str, ref: Ref = HeadRef()):
        self.branch_name = branch_name
        self.ref = ref

    def run(self, repo: Repo):
        branch(repo, self.branch_name, self.ref)

class DeleteBranches(Statement):
    def __init__(self, branch_names: list[str]):
        self.branch_names = branch_names

    def run(self, repo: Repo):
        for branch_name in self.branch_names:
            delete_branch(repo, branch_name)

class Tag(Statement):
    def __init__(self, tag_name: str):
        self.tag_name = tag_name

    def run(self, repo: Repo):
        tag(repo, self.tag_name)

class DeleteTags(Statement):
    def __init__(self, tag_names: list[str]):
        self.tag_names = tag_names

    def run(self, repo: Repo):
        for tag_name in self.tag_names:
            delete_tag(repo, tag_name)


class Config(Statement):
    def __init__(self, key: str, value: int):
        self.key = key
        self.value = value

    def run(self, repo: Repo):
        if self.key == "commit.verbose":
            repo.commit_verbose = self.value != 0
        elif self.key == "merge.verbosity":
            repo.merge_verbosity = int(self.value)
        else:
            raise RuntimeError(f"Unknown config key: {self.key}")


class DefineAlias(Statement):
    def __init__(self, name: str, fragment: str):
        self.name = name
        self.fragment = fragment

    def run(self, repo: Repo):
        repo.aliases[self.name] = AliasDefinition(self.fragment)


class DefineFunction(Statement):
    def __init__(self, name: str, parameters: list[Parameter], body: str):
        self.name = name
        self.parameters = parameters
        self.body = body

    def run(self, repo: Repo):
        repo.aliases[self.name] = FunctionDefinition(self.parameters, self.body)


class AliasCall(Statement):
    def __init__(self, name: str, args: list[str]):
        self.name = name
        self.args = args

    def run(self, repo: Repo):
        definition = repo.aliases.get(self.name)
        if definition is None:
            raise RuntimeError(f"Unknown git command or alias: {self.name}")

        if isinstance(definition, AliasDefinition):
            source = "git " + definition.fragment
            if self.args:
                source += " " + " ".join(_quote_arg(arg) for arg in self.args)
            _run_source(repo, source)
            return

        if isinstance(definition, FunctionDefinition):
            frame = _bind_function_args(definition, self.args)
            repo.call_stack.append(frame)
            try:
                _run_source(repo, _substitute_parameters(definition.body, frame))
            except ExitSignal:
                pass
            finally:
                repo.call_stack.pop()
            return

        raise RuntimeError(f"Unknown alias definition: {definition.__class__.__name__}")


class Exit(Statement):
    def run(self, repo: Repo):
        raise ExitSignal()


class Checkout(Statement):
    def __init__(self, branch_name: str, create_at: Optional[Ref] = None):
        self.branch_name = branch_name
        self.create_at = create_at

    def run(self, repo: Repo):
        if self.create_at:
            branch(repo, self.branch_name, self.create_at)
        checkout(repo, self.branch_name)

class Commit(Statement):
    def __init__(self, value: Optional[int], amend: bool):
        self.value = value
        self.amend = amend

    def run(self, repo: Repo):
        if self.value is None:
            commit(repo, int(input()), self.amend)
        else:
            commit(repo, self.value, self.amend)

class CommitString(Statement):
    def __init__(self, value: Optional[str]):
        self.value = value

    def run(self, repo: Repo):
        if self.value is None:
            commit_string(repo, input())
        else:
            commit_string(repo, self.value)

class Reset(Statement):
    def __init__(self, ref: Ref):
        self.ref = ref

    def run(self, repo: Repo):
        reset(repo, self.ref)

class CherryPick(Statement):
    def __init__(self, ref: Ref, op: Operator = Operator.THEIRS):
        self.ref = ref
        self.op = op

    def run(self, repo: Repo):
        cherry_pick(repo, self.ref, self.op)

class CherryPickRange(Statement):
    def __init__(self, commit_range: CommitRange, op: Operator = Operator.THEIRS):
        self.range = commit_range
        self.op = op

    def run(self, repo: Repo):
        cherry_pick_range(repo, self.range, self.op)

class Revert(Statement):
    def __init__(self, ref: Ref):
        self.ref = ref

    def run(self, repo: Repo):
        revert(repo, self.ref)

class RevertRange(Statement):
    def __init__(self, commit_range: CommitRange):
        self.range = commit_range

    def run(self, repo: Repo):
        revert_range(repo, self.range)

class Rebase(Statement):
    def __init__(self, ref: Ref):
        self.ref = ref

    def run(self, repo: Repo):
        rebase(repo, self.ref)

class Show(Statement):
    def __init__(self, ref: Ref = HeadRef()):
        self.ref = ref

    def run(self, repo: Repo):
        show(repo, self.ref)

class Log(Statement):
    def __init__(self, ref: Ref = HeadRef(), limit: Optional[int] = None, reverse: bool = False):
        self.ref = ref
        self.limit = limit
        self.reverse = reverse

    def run(self, repo: Repo):
        log(repo, self.ref, self.limit, self.reverse)

class LogRange(Statement):
    def __init__(self, commit_range: CommitRange, limit: Optional[int] = None, reverse: bool = False):
        self.commit_range = commit_range
        self.limit = limit
        self.reverse = reverse

    def run(self, repo: Repo):
        log_range(repo, self.commit_range, self.limit, self.reverse)


class RevList(Statement):
    def __init__(self, ref: Ref = HeadRef(), limit: Optional[int] = None, reverse: bool = False):
        self.ref = ref
        self.limit = limit
        self.reverse = reverse

    def run(self, repo: Repo):
        rev_list(repo, self.ref, self.limit, self.reverse)


class RevListRange(Statement):
    def __init__(self, commit_range: CommitRange, limit: Optional[int] = None, reverse: bool = False):
        self.commit_range = commit_range
        self.limit = limit
        self.reverse = reverse

    def run(self, repo: Repo):
        rev_list_range(repo, self.commit_range, self.limit, self.reverse)


class MergeContinue(Statement):
    def __init__(self, label: Optional[str] = None):
        self.label = label

    def run(self, repo: Repo):
        raise MergeContinueSignal(self.label)


class MergeAbort(Statement):
    def __init__(self, label: Optional[str] = None):
        self.label = label

    def run(self, repo: Repo):
        raise MergeAbortSignal(self.label)

class Conflict(Statement):
    def __init__(
            self,
            ref_a: Ref,
            ref_b: Ref,
            block_a: list[Statement],
            block_b: list[Statement],
            condition: Condition = Condition.EQ,
            label: Optional[str] = None,
    ):
        self.ref_a = ref_a
        self.ref_b = ref_b
        self.block_a = block_a
        self.block_b = block_b
        self.condition = condition
        self.label = label

    def run(self, repo: Repo):
        while True:
            _log_merge_begin(repo, self.label, self.condition)
            commit_a = resolve(self.ref_a, repo)
            commit_b = resolve(self.ref_b, repo)
            condition_matches = _condition_matches(commit_a, commit_b, self.condition)
            block_name = "top" if condition_matches else "bottom"
            _log_merge_check(repo, self.label, self.condition, commit_a.value, commit_b.value, block_name)
            block = self.block_a if condition_matches else self.block_b

            try:
                for statement in block:
                    statement.run(repo)
            except MergeContinueSignal as signal:
                if signal.label is not None and signal.label != self.label:
                    raise
                _log_merge_signal(repo, "continue", signal.label, self.label)
                continue
            except MergeAbortSignal as signal:
                if signal.label is not None and signal.label != self.label:
                    raise
                _log_merge_signal(repo, "abort", signal.label, self.label)
                break

            break


def _condition_matches(commit_a, commit_b, condition: Condition) -> bool:
    if condition == Condition.IS:
        return commit_a is commit_b

    value_a = commit_a.value
    value_b = commit_b.value

    if condition == Condition.GT:
        return value_a > value_b
    if condition == Condition.LT:
        return value_a < value_b
    if condition == Condition.EQ:
        return value_a == value_b
    if condition == Condition.NEQ:
        return value_a != value_b
    if condition == Condition.GTE:
        return value_a >= value_b
    if condition == Condition.LTE:
        return value_a <= value_b

    raise RuntimeError(f"Unknown condition: {condition}")


def _label_text(label: Optional[str]) -> str:
    return "<none>" if label is None else label


def _log_merge_begin(repo: Repo, label: Optional[str], condition: Condition) -> None:
    if repo.merge_verbosity < 1:
        return
    print(f"[merge] begin label={_label_text(label)} condition={condition.value}", file=sys.stderr)


def _log_merge_check(
        repo: Repo,
        label: Optional[str],
        condition: Condition,
        value_a: int,
        value_b: int,
        selected: str,
) -> None:
    if repo.merge_verbosity < 1:
        return
    print(
        f"[merge] check label={_label_text(label)} condition={condition.value} "
        f"left={value_a} right={value_b} selected={selected}",
        file=sys.stderr,
    )


def _log_merge_signal(repo: Repo, signal: str, target: Optional[str], handled_by: Optional[str]) -> None:
    if repo.merge_verbosity < 2:
        return
    print(
        f"[merge] {signal} target={_label_text(target)} handled_by={_label_text(handled_by)}",
        file=sys.stderr,
    )


def _quote_arg(arg: str) -> str:
    return shlex.quote(arg)


def _bind_function_args(definition: FunctionDefinition, args: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    positional: list[str] = []
    named: dict[str, str] = {}
    i = 0

    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            name_value = arg[2:]
            if not name_value:
                raise RuntimeError("Named argument needs a name")
            if "=" in name_value:
                name, value = name_value.split("=", 1)
                i += 1
            else:
                if i + 1 >= len(args):
                    raise RuntimeError(f"Named argument --{name_value} needs a value")
                name = name_value
                value = args[i + 1]
                i += 2
            if name in named:
                raise RuntimeError(f"Parameter {name} supplied more than once")
            named[name] = value
        else:
            positional.append(arg)
            i += 1

    parameters = definition.parameters
    if len(positional) > len(parameters):
        raise RuntimeError("Function called with too many positional arguments")

    for parameter, value in zip(parameters, positional):
        values[parameter.name] = _validate_parameter_value(parameter, value)

    for name, value in named.items():
        parameter = next((p for p in parameters if p.name == name), None)
        if parameter is None:
            raise RuntimeError(f"Unknown parameter: {name}")
        if name in values:
            raise RuntimeError(f"Parameter {name} supplied more than once")
        values[name] = _validate_parameter_value(parameter, value)

    for parameter in parameters:
        if parameter.name in values:
            continue
        if parameter.default is None:
            raise RuntimeError(f"Missing function argument: {parameter.name}")
        values[parameter.name] = parameter.default

    return values


def _validate_parameter_value(parameter: Parameter, value: str) -> str:
    if parameter.kind == "-i":
        return str(_parse_integer_literal(value))
    if parameter.kind == "-s":
        return value
    if parameter.kind == "-l":
        _validate_name(value, "parameter")
        return value
    if parameter.kind == "-r":
        return value
    if parameter.kind == "-c":
        if not any(condition.value == value for condition in Condition):
            raise RuntimeError(f"Unknown merge condition: {value}")
        return value
    if parameter.kind == "-o":
        if not any(operator.value == value for operator in Operator):
            raise RuntimeError(f"Unknown strategy: {value}")
        return value
    raise RuntimeError(f"Unknown parameter type: {parameter.kind}")


def _parse_integer_literal(value: str) -> int:
    if value == "true":
        return 1
    if value == "false":
        return 0
    return int(value)


def _validate_name(value: str, kind: str) -> None:
    if value == "HEAD":
        raise RuntimeError(f"{kind} name cannot be HEAD")
    if value.startswith("-"):
        raise RuntimeError(f"{kind} name cannot start with -")
    if any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_/" for char in value):
        raise RuntimeError(f"{kind} name may contain only A-Z, a-z, 0-9, -, _, and /")


def _substitute_parameters(source: str, frame: dict[str, str]) -> str:
    def replace(match):
        name = match.group(1)
        if name not in frame:
            raise RuntimeError(f"Unknown parameter: {name}")
        return frame[name]

    return re.sub(r"\$([A-Za-z0-9_/-]+)", replace, source)


def _run_source(repo: Repo, source: str) -> None:
    from gitscript.parser import parse

    for statement in parse(source):
        statement.run(repo)
