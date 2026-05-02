from typing import Optional

from gitscript.ast import Ref, resolve, HeadRef
from gitscript.commands import commit, commit_string, branch, checkout, reset, merge, show, log, tag, cherry_pick, rebase
from gitscript.operators import Operator
from gitscript.repo import Repo


class Statement:
    def run(self, repo: Repo):
        pass

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
    def __init__(self, value: Optional[str], amend: bool):
        self.value = value
        self.amend = amend

    def run(self, repo: Repo):
        if self.value is None:
            commit_string(repo, input(), self.amend)
        else:
            commit_string(repo, self.value, self.amend)

class Merge(Statement):
    def __init__(self, ref: Ref, op: Operator):
        self.ref = ref
        self.op = op

    def run(self, repo: Repo):
        merge(repo, self.ref, self.op)

class CherryPick(Statement):
    def __init__(self, ref: Ref):
        self.ref = ref
    
    def run(self, repo: Repo):
        cherry_pick(repo, self.ref)

class Rebase(Statement):
    def __init__(self, ref: Ref):
        self.ref = ref

    def run(self, repo: Repo):
        rebase(repo, self.ref)

class Branch(Statement):
    def __init__(self, branch_name: str):
        self.branch_name = branch_name

    def run(self, repo: Repo):
        branch(repo, self.branch_name)

class Tag(Statement):
    def __init__(self, tag_name: str):
        self.tag_name = tag_name

    def run(self, repo: Repo):
        tag(repo, self.tag_name)

class Checkout(Statement):
    def __init__(self, branch_name: str, create_branch: bool):
        self.branch_name = branch_name
        self.create_branch = create_branch

    def run(self, repo: Repo):
        if self.create_branch:
            branch(repo, self.branch_name)
        checkout(repo, self.branch_name)

class Reset(Statement):
    def __init__(self, ref: Ref):
        self.ref = ref

    def run(self, repo: Repo):
        reset(repo, self.ref)

class Show(Statement):
    def __init__(self, ref: Ref = HeadRef()):
        self.ref = ref

    def run(self, repo: Repo):
        show(repo, self.ref)

class Log(Statement):
    def __init__(self, ref: Ref = HeadRef()):
        self.ref = ref

    def run(self, repo: Repo):
        log(repo, self.ref)

class Conflict(Statement):
    def __init__(self, ref_a: Ref, block_a: list[Statement], ref_b: Ref, block_b: list[Statement]):
        self.ref_a = ref_a
        self.block_a = block_a
        self.ref_b = ref_b
        self.block_b = block_b

    def run(self, repo: Repo):
        while True:
            value_a = resolve(self.ref_a, repo).value
            value_b = resolve(self.ref_b, repo).value

            if value_a > value_b:
                for statement in self.block_a:
                    statement.run(repo)
            elif value_a < value_b:
                for statement in self.block_b:
                    statement.run(repo)
            else:
                break
