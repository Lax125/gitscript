import contextlib
import io
import unittest
from unittest.mock import patch

from gitscript.refs import BranchRef, ConstantOffsetRef, HeadRef
from gitscript.operators import Operator
from gitscript.repo import Repo
from gitscript.statements import (
    Branch,
    Checkout,
    CherryPick,
    Commit,
    CommitString,
    Conflict,
    Log,
    Merge,
    Rebase,
    Reset,
    Show,
    Tag,
)


def capture_output(statement, repo: Repo) -> str:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        statement.run(repo)
    return output.getvalue()


def values_from_head(repo: Repo, ref_name: str = "main") -> list[int]:
    values = []
    commit = repo.resolve(ref_name)

    while commit is not None:
        values.append(commit.value)
        commit = commit.parent

    return values


class StatementTests(unittest.TestCase):
    def test_commit_creates_commit_with_value_and_parent(self):
        repo = Repo()
        root = repo.branches["main"]

        Commit(5, amend=False).run(repo)

        head = repo.branches["main"]
        self.assertEqual(head.value, 5)
        self.assertIs(head.parent, root)
        self.assertEqual(values_from_head(repo), [5, 0])

    def test_commit_can_read_value_from_input(self):
        repo = Repo()

        with patch("builtins.input", return_value="9"):
            Commit(None, amend=False).run(repo)

        self.assertEqual(repo.branches["main"].value, 9)

    def test_commit_amend_uses_current_parent(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)
        original = repo.branches["main"]

        Commit(2, amend=True).run(repo)

        head = repo.branches["main"]
        self.assertEqual(head.value, 2)
        self.assertIs(head.parent, original.parent)
        self.assertEqual(values_from_head(repo), [2, 0])

    def test_commit_string_stores_null_terminated_reversed_chain(self):
        repo = Repo()
        root = repo.branches["main"]

        CommitString("Hi", amend=False).run(repo)

        head = repo.branches["main"]
        self.assertEqual(values_from_head(repo), [ord("H"), ord("i"), 0, 0])
        self.assertIs(head.parent.parent.parent, root)

    def test_commit_string_can_read_value_from_input(self):
        repo = Repo()

        with patch("builtins.input", return_value="Yo"):
            CommitString(None, amend=False).run(repo)

        self.assertEqual(values_from_head(repo)[:3], [ord("Y"), ord("o"), 0])

    def test_branch_creates_new_pointer_at_current_commit(self):
        repo = Repo()
        Commit(7, amend=False).run(repo)

        Branch("seven").run(repo)

        self.assertIn("seven", repo.branches)
        self.assertIs(repo.branches["seven"], repo.branches["main"])
        self.assertEqual(repo.branches["seven"].value, 7)

    def test_tag_creates_named_pointer_at_current_commit(self):
        repo = Repo()
        Commit(8, amend=False).run(repo)

        Tag("eight").run(repo)

        self.assertIn("eight", repo.tags)
        self.assertIs(repo.tags["eight"], repo.branches["main"])
        self.assertEqual(repo.tags["eight"].value, 8)

    def test_checkout_switches_head_and_can_create_branch(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)

        Checkout("feature", create_branch=True).run(repo)
        Commit(2, amend=False).run(repo)
        Checkout("main", create_branch=False).run(repo)

        self.assertEqual(repo.HEAD, "main")
        self.assertEqual(repo.branches["main"].value, 1)
        self.assertEqual(repo.branches["feature"].value, 2)

    def test_reset_moves_current_branch_to_ref(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)
        Commit(2, amend=False).run(repo)

        Reset(ConstantOffsetRef(HeadRef(), 1)).run(repo)

        self.assertEqual(repo.branches["main"].value, 1)
        self.assertEqual(values_from_head(repo), [1, 0])

    def test_merge_creates_commit_from_head_and_ref_values(self):
        repo = Repo()
        Commit(10, amend=False).run(repo)
        Branch("ten").run(repo)
        Commit(3, amend=False).run(repo)

        Merge(BranchRef("ten"), Operator.SUBTRACT).run(repo)

        self.assertEqual(repo.branches["main"].value, -7)
        self.assertEqual(repo.branches["main"].parent.value, 3)
        self.assertEqual(repo.branches["ten"].value, 10)

    def test_cherry_pick_copies_value_from_ref(self):
        repo = Repo()
        Commit(4, amend=False).run(repo)
        Branch("four").run(repo)
        Commit(9, amend=False).run(repo)

        CherryPick(BranchRef("four")).run(repo)

        self.assertEqual(repo.branches["main"].value, 4)
        self.assertEqual(repo.branches["main"].parent.value, 9)

    def test_rebase_replays_current_branch_values_onto_ref(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)
        Checkout("feature", create_branch=True).run(repo)
        Commit(2, amend=False).run(repo)
        Commit(3, amend=False).run(repo)
        Checkout("main", create_branch=False).run(repo)
        Commit(9, amend=False).run(repo)
        Checkout("feature", create_branch=False).run(repo)

        Rebase(BranchRef("main")).run(repo)

        self.assertEqual(values_from_head(repo, "feature"), [3, 2, 9, 1, 0])
        self.assertIs(repo.branches["feature"].parent.parent, repo.branches["main"])

    def test_show_prints_selected_commit_value(self):
        repo = Repo()
        Commit(11, amend=False).run(repo)
        Commit(12, amend=False).run(repo)

        output = capture_output(Show(ConstantOffsetRef(HeadRef(), 1)), repo)

        self.assertEqual(output, "11\n")

    def test_log_prints_string_from_selected_commit_chain(self):
        repo = Repo()
        CommitString("Ok", amend=False).run(repo)

        output = capture_output(Log(HeadRef()), repo)

        self.assertEqual(output, "Ok\n")

    def test_conflict_runs_blocks_until_ref_values_match(self):
        repo = Repo()
        Checkout("a", create_branch=True).run(repo)
        Commit(48, amend=False).run(repo)
        Checkout("b", create_branch=True).run(repo)
        Commit(18, amend=False).run(repo)

        Conflict(
            BranchRef("a"),
            [Checkout("a", create_branch=False), Merge(BranchRef("b"), Operator.SUBTRACT)],
            BranchRef("b"),
            [Checkout("b", create_branch=False), Merge(BranchRef("a"), Operator.SUBTRACT)],
        ).run(repo)

        self.assertEqual(repo.branches["a"].value, 6)
        self.assertEqual(repo.branches["b"].value, 6)
        self.assertEqual(repo.HEAD, "a")


if __name__ == "__main__":
    unittest.main()
