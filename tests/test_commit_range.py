import unittest

from gitscript.commit_range import CommitRange
from gitscript.commands import branch, checkout, commit
from gitscript.refs import BranchRef, ConstantOffsetRef, HeadRef
from gitscript.repo import Repo


class CommitRangeTests(unittest.TestCase):
    def test_resolve_returns_include_reachable_commits_until_excluded_ancestor(self):
        repo = Repo()
        commit(repo, 1)
        commit(repo, 2)
        commit(repo, 3)

        commits = CommitRange(ConstantOffsetRef(HeadRef(), 2), HeadRef()).resolve(repo)

        self.assertEqual([commit.value for commit in commits], [3, 2])

    def test_resolve_returns_empty_range_when_refs_are_equal(self):
        repo = Repo()
        commit(repo, 1)

        commits = CommitRange(HeadRef(), HeadRef()).resolve(repo)

        self.assertEqual(commits, [])

    def test_resolve_excludes_all_ancestors_reachable_from_exclude(self):
        repo = Repo()
        commit(repo, 1)
        branch(repo, "base")
        commit(repo, 2)
        branch(repo, "feature")
        checkout(repo, "base")
        commit(repo, 9)
        branch(repo, "main-tip")

        commits = CommitRange(BranchRef("main-tip"), BranchRef("feature")).resolve(repo)

        self.assertEqual([commit.value for commit in commits], [2])


if __name__ == "__main__":
    unittest.main()
