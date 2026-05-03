from gitscript.commit import Commit
from gitscript.refs import Ref
from gitscript.repo import Repo


class CommitRange:
    def __init__(self, exclude: Ref, include: Ref):
        self.exclude = exclude
        self.include = include

    def resolve(self, repo: Repo) -> list[Commit]:
        excluded = set()
        commit = self.exclude.resolve(repo)
        while commit is not None:
            excluded.add(commit)
            commit = commit.parent

        commits = []
        commit = self.include.resolve(repo)
        while commit is not None and commit not in excluded:
            commits.append(commit)
            commit = commit.parent

        return commits
