from typing import Optional

from gitscript.commit_range import CommitRange
from gitscript.refs import resolve, Ref, HeadRef
from gitscript.commit import Commit
from gitscript.operators import Operator
from gitscript.repo import Repo


def commit(repo: Repo, value: int, amend=False):
    head = repo.branches[repo.HEAD]

    parent = head.parent if amend else head

    new = Commit(value, parent)

    # move branch
    repo.branches[repo.HEAD] = new

def commit_string(repo: Repo, value: str):
    head = repo.branches[repo.HEAD]

    parent = head
    new = parent

    for char in value[::-1]:
        new = Commit(ord(char), parent)
        parent = new

    # move branch
    repo.branches[repo.HEAD] = new

def cherry_pick(repo: Repo, ref: Ref):
    c = ref.resolve(repo)
    commit(repo, c.value)

def cherry_pick_range(repo: Repo, commit_range: CommitRange):
    # reverse resolved range to get back chronological ordering
    for c in commit_range.resolve(repo)[::-1]:
        commit(repo, c.value)

def revert(repo: Repo, ref: Ref):
    c = ref.resolve(repo)
    commit(repo, -c.value)

def revert_range(repo: Repo, commit_range: CommitRange):
    for c in commit_range.resolve(repo):
        commit(repo, -c.value)

def merge(repo, ref, op: Operator):
    a = repo.branches[repo.HEAD].value
    b = resolve(ref, repo).value

    if op == Operator.ADD: v = a + b
    elif op == Operator.SUBTRACT: v = a - b
    elif op == Operator.MULTIPLY: v = a * b
    elif op == Operator.DIVIDE: v = a // b
    elif op == Operator.MODULO: v = a % b
    elif op == Operator.GT: v = int(a > b) * 2 - 1
    elif op == Operator.LT: v = int(a < b) * 2 - 1
    elif op == Operator.EQ: v = int(a == b) * 2 - 1
    elif op == Operator.NEQ: v = int(a != b) * 2 - 1
    elif op == Operator.GTE: v = int(a >= b) * 2 - 1
    elif op == Operator.LTE: v = int(a <= b) * 2 - 1
    else:
        raise RuntimeError(f"Unknown strategy: {op}")

    commit(repo, v)

def reset(repo, ref):
    repo.branches[repo.HEAD] = resolve(ref, repo)

def branch(repo: Repo, name: str, ref: Ref = HeadRef()):
    if repo.has(name):
        raise RuntimeError(f"Branch or tag {name} already exists")
    c = resolve(ref, repo)
    repo.branches[name] = c

def delete_branch(repo: Repo, name: str):
    if repo.HEAD == name:
        raise RuntimeError(f"Cannot delete current branch {name}")
    elif name not in repo.branches:
        raise RuntimeError(f"Branch {name} does not exist")
    del repo.branches[name]

def checkout(repo: Repo, name: str):
    if name not in repo.branches:
        raise RuntimeError(f"Branch {name} does not exist")
    repo.HEAD = name

def tag(repo: Repo, name: str):
    if repo.has(name):
        raise RuntimeError(f"Branch or tag {name} already exists")
    c = repo.branches[repo.HEAD]
    repo.tags[name] = c

def delete_tag(repo: Repo, name: str):
    if name not in repo.tags:
        raise RuntimeError(f"tag {name} does not exist")
    del repo.tags[name]

def rebase(repo, ref):
    head = repo.branches[repo.HEAD]
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
        base = Commit(old.value, base)

    # update branch
    repo.branches[repo.HEAD] = base

def show(repo: Repo, ref: Ref):
    c = resolve(ref, repo)
    print(c.value)

def log(repo: Repo, ref: Ref, limit: Optional[int] = None, reverse: bool = False):
    print(_commits_to_string(_select_commits(_reachable_commits(resolve(ref, repo)), limit, reverse)))

def log_range(repo: Repo, commit_range: CommitRange, limit: Optional[int] = None, reverse: bool = False):
    print(_commits_to_string(_select_commits(commit_range.resolve(repo), limit, reverse)))

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


def _print_values(commits: list[Commit]) -> None:
    for c in commits:
        print(c.value)
