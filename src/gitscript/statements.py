from typing import Optional

from gitscript.commit_range import CommitRange
from gitscript.refs import Ref, resolve, HeadRef
from gitscript.commands import commit, commit_string, branch, checkout, reset, merge, show, log, tag, cherry_pick, \
    rebase, delete_branch, delete_tag, cherry_pick_range, revert, revert_range, log_range, rev_list, rev_list_range
from gitscript.operators import Operator
from gitscript.repo import Repo


class Statement:
    def run(self, repo: Repo):
        pass

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

class CherryPickRange(Statement):
    def __init__(self, commit_range: CommitRange):
        self.range = commit_range

    def run(self, repo: Repo):
        cherry_pick_range(repo, self.range)

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

class Conflict(Statement):
    def __init__(self, ref_a: Ref, ref_b: Ref, block_a: list[Statement], block_b: list[Statement]):
        self.ref_a = ref_a
        self.ref_b = ref_b
        self.block_a = block_a
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
