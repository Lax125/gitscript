import sys
from typing import Optional

from gitscript.commit_range import CommitRange
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

def revert(repo: Repo, ref: Ref):
    c = ref.resolve(repo)
    commit(repo, -c.value, operation="git revert")

def revert_range(repo: Repo, commit_range: CommitRange):
    for c in commit_range.resolve(repo):
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

def tag(repo: Repo, name: str):
    repo.create_tag(name, repo.current_commit())

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

def log(repo: Repo, ref: Ref, limit: Optional[int] = None, reverse: bool = False, oneline: bool = False):
    _print_string(_commits_to_string(_select_commits(_reachable_commits(resolve(ref, repo)), limit, reverse)), oneline)

def log_range(repo: Repo, commit_range: CommitRange, limit: Optional[int] = None, reverse: bool = False, oneline: bool = False):
    _print_string(_commits_to_string(_select_commits(commit_range.resolve(repo), limit, reverse)), oneline)

def rev_list(repo: Repo, ref: Ref, limit: Optional[int] = None, reverse: bool = False):
    _print_values(_select_commits(_reachable_commits(resolve(ref, repo)), limit, reverse))

def rev_list_range(repo: Repo, commit_range: CommitRange, limit: Optional[int] = None, reverse: bool = False):
    _print_values(_select_commits(commit_range.resolve(repo), limit, reverse))


def _reachable_commits(c: Commit) -> list[Commit]:
    commits = []
    while c is not None:
        commits.append(c)
        c = c.parent
    return commits


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


def _create_commit(repo: Repo, value: int, parent: Optional[Commit], operation: str) -> Commit:
    new = Commit(value, parent)
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
