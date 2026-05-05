from __future__ import annotations

from gitscript.commit import Commit
from gitscript.refs import Ref
from gitscript.repo import Repo


class CommitRange:
    def __init__(self, exclude: Ref, include: Ref):
        self.exclude = exclude
        self.include = include

    def resolve(self, repo: Repo) -> list[Commit]:
        return resolve_commit_selectors(repo, [self], ref_includes_reachable=False)

    def included_commits(self, repo: Repo) -> set[Commit]:
        return set(reachable_commits(self.include.resolve(repo)))

    def excluded_commits(self, repo: Repo) -> set[Commit]:
        return set(reachable_commits(self.exclude.resolve(repo)))


class SymmetricDifferenceRange:
    def __init__(self, left: Ref, right: Ref):
        self.left = left
        self.right = right

    def resolve(self, repo: Repo) -> list[Commit]:
        return resolve_commit_selectors(repo, [self], ref_includes_reachable=False)

    def included_commits(self, repo: Repo) -> set[Commit]:
        return set(reachable_commits(self.left.resolve(repo))) | set(reachable_commits(self.right.resolve(repo)))

    def excluded_commits(self, repo: Repo) -> set[Commit]:
        left = set(reachable_commits(self.left.resolve(repo)))
        right = set(reachable_commits(self.right.resolve(repo)))
        return left & right


CommitSelector = Ref | CommitRange | SymmetricDifferenceRange


def resolve_commit_selectors(
        repo: Repo,
        selectors: list[CommitSelector],
        ref_includes_reachable: bool,
        include_all: bool = False,
) -> list[Commit]:
    included: set[Commit] = set()
    excluded: set[Commit] = set()

    for selector in selectors:
        if isinstance(selector, Ref):
            commit = selector.resolve(repo)
            if ref_includes_reachable:
                included.update(reachable_commits(commit))
            else:
                included.add(commit)
            continue

        included.update(selector.included_commits(repo))
        excluded.update(selector.excluded_commits(repo))

    if include_all:
        all_included: set[Commit] = set()
        for commit in repo.visible_commits():
            all_included.update(reachable_commits(commit))
        return sort_backwards_chronologically((included - excluded) | all_included)

    return sort_backwards_chronologically(included - excluded)


def reachable_commits(commit: Commit) -> list[Commit]:
    commits = []
    while commit is not None:
        commits.append(commit)
        commit = commit.parent
    return commits


def sort_backwards_chronologically(commits: set[Commit]) -> list[Commit]:
    return sorted(commits, key=lambda commit: commit.order, reverse=True)
