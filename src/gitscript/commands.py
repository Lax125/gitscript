from gitscript.ast import resolve, Ref
from gitscript.commit import Commit
from gitscript.operators import Operator
from gitscript.repo import Repo


def commit(repo: Repo, value: int, amend=False):
    head = repo.branches[repo.HEAD]

    parent = head.parent if amend else head

    new = Commit(value, parent)

    # move branch
    repo.branches[repo.HEAD] = new

def commit_string(repo: Repo, value: str, amend=False):
    head = repo.branches[repo.HEAD]

    parent = head.parent if amend else head
    new = Commit(0, parent)

    parent = new

    for char in value[::-1]:
        new = Commit(ord(char), parent)
        parent = new

    # move branch
    repo.branches[repo.HEAD] = new

def cherry_pick(repo: Repo, ref: Ref):
    c = resolve(ref, repo)
    commit(repo, c.value)

def revert(repo: Repo):
    c = repo.branches[repo.HEAD]
    if c.parent:
        commit(repo, c.parent.value)
    else:
        commit(repo, 0)

def merge(repo, ref, op: Operator):
    a = repo.branches[repo.HEAD].value
    b = resolve(ref, repo).value

    if op == Operator.ADD: v = a + b
    elif op == Operator.SUBTRACT: v = a - b
    elif op == Operator.MULTIPLY: v = a * b
    elif op == Operator.DIVIDE: v = a // b
    elif op == Operator.MODULO: v = a % b
    elif op == Operator.GT: v = int(a > b)
    elif op == Operator.LT: v = int(a < b)
    elif op == Operator.EQ: v = int(a == b)
    elif op == Operator.NEQ: v = int(a != b)
    elif op == Operator.GTE: v = int(a >= b)
    elif op == Operator.LTE: v = int(a <= b)
    else:
        raise RuntimeError(f"Unknown strategy: {op}")

    commit(repo, v)

def reset(repo, ref):
    repo.branches[repo.HEAD] = resolve(ref, repo)

def branch(repo: Repo, name: str):
    if repo.has(name):
        raise RuntimeError(f"Branch or tag {name} already exists")
    c = repo.branches[repo.HEAD]
    repo.branches[name] = c

def checkout(repo: Repo, name: str):
    if name not in repo.branches:
        raise RuntimeError(f"Branch {name} does not exist")
    repo.HEAD = name

def tag(repo: Repo, name: str):
    if repo.has(name):
        raise RuntimeError(f"Branch or tag {name} already exists")
    c = repo.branches[repo.HEAD]
    repo.tags[name] = c

def untag(repo: Repo, name: str):
    if tag not in repo.tags:
        raise RuntimeError(f"tag {name} does not exist")
    del repo.tags[tag]

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

def log(repo: Repo, ref: Ref):
    c = resolve(ref, repo)
    string = ""

    while c.value:
        string += chr(c.value)
        if not c.parent:
            break
        c = c.parent

    print(string)
