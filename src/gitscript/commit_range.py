from gitscript.commit import Commit
from gitscript.refs import Ref
from gitscript.repo import Repo


class CommitRange:
    def __init__(self, exclude: Ref, include: Ref):
        self.exclude = exclude
        self.include = include

    def resolve(self, repo: Repo) -> list[Commit]:
        pass # TODO implement. this should return all commits reachable from include but not from exclude, in reverse chronological order
