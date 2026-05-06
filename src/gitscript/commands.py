import sys
from typing import Optional

from gitscript.commit_range import CommitRange, CommitSelector, resolve_commit_selectors
from gitscript.refs import resolve, Ref, HeadRef
from gitscript.commit import Commit
from gitscript.operators import Operator
from gitscript.repo import Repo


def commit(repo: Repo, value: int, amend=False, operation: str = "git commit"):
    head = repo.current_commit()

    parent = head.parent if amend else head

    new = _create_commit(repo, value, parent, operation)

    # move branch
    repo.set_current_commit(new)

def commit_string(repo: Repo, value: str):
    head = repo.current_commit()

    parent = head
    new = parent

    for char in value[::-1]:
        new = _create_commit(repo, ord(char), parent, "git commit string")
        parent = new

    # move branch
    repo.set_current_commit(new)

def cherry_pick(repo: Repo, ref: Ref, op: Operator = Operator.THEIRS):
    c = ref.resolve(repo)
    commit(repo, _apply_operator(repo.current_commit().value, c.value, op), operation="git cherry-pick")

def cherry_pick_range(repo: Repo, commit_range: CommitRange, op: Operator = Operator.THEIRS):
    # reverse resolved range to get back chronological ordering
    for c in commit_range.resolve(repo)[::-1]:
        commit(repo, _apply_operator(repo.current_commit().value, c.value, op), operation="git cherry-pick range")

def cherry_pick_selectors(repo: Repo, selectors: list[CommitSelector], op: Operator = Operator.THEIRS):
    for c in resolve_commit_selectors(repo, selectors, ref_includes_reachable=False)[::-1]:
        commit(repo, _apply_operator(repo.current_commit().value, c.value, op), operation="git cherry-pick range")

def revert(repo: Repo, ref: Ref):
    c = ref.resolve(repo)
    commit(repo, -c.value, operation="git revert")

def revert_range(repo: Repo, commit_range: CommitRange):
    for c in commit_range.resolve(repo):
        commit(repo, -c.value, operation="git revert range")

def revert_selectors(repo: Repo, selectors: list[CommitSelector]):
    for c in resolve_commit_selectors(repo, selectors, ref_includes_reachable=False):
        commit(repo, -c.value, operation="git revert range")

def reset(repo, ref):
    repo.set_current_commit(resolve(ref, repo))

def branch(repo: Repo, name: str, ref: Ref = HeadRef()):
    c = resolve(ref, repo)
    repo.create_branch(name, c)

def delete_branch(repo: Repo, name: str):
    repo.delete_branch(name)

def checkout(repo: Repo, name: str):
    repo.checkout(name)

def tag(repo: Repo, name: str, ref: Ref = HeadRef()):
    repo.create_tag(name, resolve(ref, repo))

def delete_tag(repo: Repo, name: str):
    repo.delete_tag(name)

def rebase(repo, ref):
    head = repo.current_commit()
    target = resolve(ref, repo)

    # find ancestors of target
    seen = set()
    c = target
    while c:
        seen.add(c)
        c = c.parent

    # collect commits to replay
    stack = []
    c = head
    while c not in seen:
        stack.append(c)
        c = c.parent

    base = target

    # replay in forward order
    for old in reversed(stack):
        base = _create_commit(repo, old.value, base, "git rebase")

    # update branch
    repo.set_current_commit(base)

def show(repo: Repo, ref: Ref):
    c = resolve(ref, repo)
    print(c.value)

def log(
        repo: Repo,
        ref: Ref,
        limit: Optional[int] = None,
        reverse: bool = False,
        oneline: bool = False,
        graph: bool = False,
        include_all: bool = False,
):
    commits = _select_commits(resolve_commit_selectors(repo, [ref], True, include_all), limit, reverse)
    if graph:
        _print_graph(repo, commits)
        return
    _print_string(_commits_to_string(commits), oneline)

def log_range(
        repo: Repo,
        commit_range: CommitRange,
        limit: Optional[int] = None,
        reverse: bool = False,
        oneline: bool = False,
        graph: bool = False,
        include_all: bool = False,
):
    log_selectors(repo, [commit_range], limit, reverse, oneline, graph, include_all)

def log_selectors(
        repo: Repo,
        selectors: list[CommitSelector],
        limit: Optional[int] = None,
        reverse: bool = False,
        oneline: bool = False,
        graph: bool = False,
        include_all: bool = False,
):
    commits = resolve_commit_selectors(repo, selectors, ref_includes_reachable=True, include_all=include_all)
    commits = _select_commits(commits, limit, reverse)
    if graph:
        _print_graph(repo, commits)
        return
    _print_string(_commits_to_string(commits), oneline)

def rev_list(repo: Repo, ref: Ref, limit: Optional[int] = None, reverse: bool = False, include_all: bool = False):
    _print_values(_select_commits(resolve_commit_selectors(repo, [ref], True, include_all), limit, reverse))

def rev_list_range(
        repo: Repo,
        commit_range: CommitRange,
        limit: Optional[int] = None,
        reverse: bool = False,
        include_all: bool = False,
):
    rev_list_selectors(repo, [commit_range], limit, reverse, include_all)

def rev_list_selectors(
        repo: Repo,
        selectors: list[CommitSelector],
        limit: Optional[int] = None,
        reverse: bool = False,
        include_all: bool = False,
):
    commits = resolve_commit_selectors(repo, selectors, ref_includes_reachable=True, include_all=include_all)
    _print_values(_select_commits(commits, limit, reverse))


def _select_commits(commits: list[Commit], limit: Optional[int], reverse: bool) -> list[Commit]:
    if limit is not None:
        commits = commits[:limit]
    if reverse:
        commits = commits[::-1]
    return commits


def _commits_to_string(commits: list[Commit]) -> str:
    return "".join(chr(c.value) for c in commits)


def _print_string(text: str, oneline: bool) -> None:
    print(text, end="" if oneline else "\n")


def _print_values(commits: list[Commit]) -> None:
    for c in commits:
        print(c.value)


def _print_graph(repo: Repo, commits: list[Commit]) -> None:
    selected = set(commits)
    annotations = repo.visible_commit_annotations()
    columns: list[Commit | object | None] = []

    for c in commits:
        column = _find_column(columns, c)
        is_new = False
        if column is None:
            is_new = True
            column = _allocate_column(columns)

        next_columns = columns.copy()

        # clear ended columns first so they can be reused

        parent = c.parent
        parent_column = _find_column(columns, parent)
        if parent in selected:
            if parent_column is None:
                parent_column = column
                next_columns[column] = parent
            elif parent_column != column:
                next_columns[column] = None
        else:
            next_columns[column] = None

        while next_columns and next_columns[-1] is None:
            next_columns.pop()

        print(
            f"{_graph_prefix(columns, column, parent_column, is_new)}{c.order} value={c.value} char={_format_graph_char(c.value)}"
            f"{_format_annotations(annotations.get(c, []))}"
        )

        columns = next_columns


def _find_column(columns: list[Commit | object | None], c: Commit) -> int | None:
    if c is None:
        return None
    for i, column_commit in enumerate(columns):
        if column_commit is c:
            return i
    return None


def _allocate_column(columns: list[Commit | object | None]) -> int:
    for i in range(len(columns)):
        if columns[i] is None:
            return i
    columns.append(None)
    return len(columns) - 1


def _graph_prefix(columns: list[Commit | object | None], commit_column: int, parent_column: int | None, is_new: bool) -> str:
    columns_to_print = columns.copy()
    while len(columns_to_print) > commit_column + 1 and columns_to_print[-1] is None:
        columns_to_print.pop()

    cells = []
    for i in range(len(columns_to_print)):
        if i == commit_column:
            if parent_column is None or parent_column < commit_column:
                if is_new:
                    cells.append("═ ")
                else:
                    cells.append("╧ ")
            elif parent_column > commit_column:
                if is_new:
                    cells.append("═─")
                else:
                    cells.append("╧─")
            elif is_new:
                cells.append("╤ ")
            else:
                cells.append("╪ ")
        elif i == parent_column:
            if commit_column < parent_column:
                cells.append("┤ ")
            else:
                cells.append("├─")
        elif columns_to_print[i] is not None:
            if parent_column is not None and parent_column < i < commit_column:
                cells.append("┼─")
            else:
                cells.append("│ ")
        elif parent_column is not None and parent_column < i < commit_column:
            cells.append("──")
        else:
            cells.append("  ")
    return "".join(cells)


def _format_annotations(annotations: list[str]) -> str:
    if not annotations:
        return ""
    return f" [{', '.join(annotations)}]"


def _format_graph_char(value: int) -> str:
    try:
        char = chr(value)
    except (ValueError, OverflowError):
        return "N/A"
    return repr(char)


def _create_commit(repo: Repo, value: int, parent: Optional[Commit], operation: str) -> Commit:
    new = repo.allocate_commit(value, parent)
    _log_commit(repo, new, parent, operation)
    return new


def _log_commit(repo: Repo, c: Commit, parent: Optional[Commit], operation: str) -> None:
    if not repo.commit_verbose:
        return

    parent_value = "none" if parent is None else str(parent.value)
    print(
        f"[commit] branch={repo.HEAD} value={c.value} parent={parent_value} operation={operation}",
        file=sys.stderr,
    )


def _apply_operator(ours: int, theirs: int, op: Operator) -> int:
    if op == Operator.OURS:
        return ours
    if op == Operator.THEIRS:
        return theirs
    if op == Operator.MIN:
        return min(ours, theirs)
    if op == Operator.MAX:
        return max(ours, theirs)
    if op == Operator.ADD:
        return ours + theirs
    if op == Operator.SUBTRACT:
        return ours - theirs
    if op == Operator.MULTIPLY:
        return ours * theirs
    if op == Operator.DIVIDE:
        return ours // theirs
    if op == Operator.MODULO:
        return ours % theirs
    if op == Operator.GT:
        return int(ours > theirs)
    if op == Operator.LT:
        return int(ours < theirs)
    if op == Operator.EQ:
        return int(ours == theirs)
    if op == Operator.NEQ:
        return int(ours != theirs)
    if op == Operator.GTE:
        return int(ours >= theirs)
    if op == Operator.LTE:
        return int(ours <= theirs)

    raise RuntimeError(f"Unknown strategy: {op}")
