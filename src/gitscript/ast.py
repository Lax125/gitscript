from gitscript.commit import Commit
from gitscript.repo import Repo


class Ref:
    pass

class HeadRef(Ref): pass
class BranchRef(Ref):
    def __init__(self, name: str): self.name = name

class AncestorRef(Ref):
    def __init__(self, base: Ref):
        self.base = base

    def offset(self, repo: Repo) -> int:
        pass

class DynamicOffsetRef(AncestorRef):
    def __init__(self, base: Ref, offset_expr: Ref):
        super().__init__(base)
        self.offset_expr = offset_expr  # another Ref

    def offset(self, repo: Repo):
        offset_commit = resolve(self.offset_expr, repo)
        return offset_commit.value

class ConstantOffsetRef(AncestorRef):
    def __init__(self, base: Ref, offset: int):
        super().__init__(base)
        self.offset = offset

    def offset(self, repo: Repo):
        return self.offset

def resolve(ref: Ref, repo: Repo) -> Commit:
    if isinstance(ref, HeadRef):
        return repo.resolve(repo.HEAD)

    if isinstance(ref, BranchRef):
        return repo.resolve(ref.name)

    if isinstance(ref, AncestorRef):
        base_commit = resolve(ref.base, repo)
        offset = ref.offset(repo)

        if offset < 0:
            raise RuntimeError("Negative offset")

        c = base_commit
        for _ in range(offset):
            if c.parent is None:
                return c  # stop at root
            c = c.parent
        return c

    raise RuntimeError(f"Unknown ref type: {ref.__class__.__name__}")
