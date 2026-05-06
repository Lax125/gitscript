import contextlib
import io
import unittest
from unittest.mock import patch

from gitscript.commit_range import CommitRange
from gitscript.refs import BranchRef, ConstantOffsetRef, HeadRef
from gitscript.operators import Condition, Operator
from gitscript.repo import Repo
from gitscript.statements import (
    Branch,
    Checkout,
    CherryPick,
    CherryPickRange,
    Commit,
    CommitString,
    Conflict,
    DeleteBranches,
    DeleteTags,
    ListBranches,
    Log,
    LogRange,
    MergeAbort,
    MergeContinue,
    Rebase,
    Revert,
    RevertRange,
    Reset,
    RevList,
    RevListRange,
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

    def test_commit_string_stores_one_commit_per_character(self):
        repo = Repo()
        root = repo.branches["main"]

        CommitString("Hi").run(repo)

        head = repo.branches["main"]
        self.assertEqual(values_from_head(repo), [ord("H"), ord("i"), 0])
        self.assertIs(head.parent.parent, root)

    def test_commit_string_can_handle_empty_string(self):
        repo = Repo()
        root = repo.branches["main"]

        CommitString("").run(repo)

        head = repo.branches["main"]
        self.assertEqual(values_from_head(repo), [0])
        self.assertIs(head, root)

    def test_commit_string_can_read_value_from_input(self):
        repo = Repo()

        with patch("builtins.input", return_value="Yo"):
            CommitString(None).run(repo)

        self.assertEqual(values_from_head(repo)[:2], [ord("Y"), ord("o")])

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

        Checkout("feature", create_at=HeadRef()).run(repo)
        Commit(2, amend=False).run(repo)
        Checkout("main").run(repo)

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

    def test_cherry_pick_strategy_creates_commit_from_head_and_ref_values(self):
        repo = Repo()
        Commit(10, amend=False).run(repo)
        Branch("ten").run(repo)
        Commit(3, amend=False).run(repo)

        CherryPick(BranchRef("ten"), Operator.SUBTRACT).run(repo)

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
        Checkout("feature", create_at=HeadRef()).run(repo)
        Commit(2, amend=False).run(repo)
        Commit(3, amend=False).run(repo)
        Checkout("main").run(repo)
        Commit(9, amend=False).run(repo)
        Checkout("feature").run(repo)

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
        CommitString("Ok").run(repo)

        output = capture_output(LogRange(CommitRange(ConstantOffsetRef(HeadRef(), 2), HeadRef())), repo)

        self.assertEqual(output, "Ok\n")

    def test_log_supports_limit_and_reverse(self):
        repo = Repo()
        Commit(65, amend=False).run(repo)
        Commit(66, amend=False).run(repo)
        Commit(67, amend=False).run(repo)

        output = capture_output(Log(HeadRef(), limit=2, reverse=True), repo)

        self.assertEqual(output, "BC\n")

    def test_log_supports_oneline(self):
        repo = Repo()
        CommitString("Prompt: ").run(repo)

        output = capture_output(LogRange(CommitRange(ConstantOffsetRef(HeadRef(), 8), HeadRef()), oneline=True), repo)

        self.assertEqual(output, "Prompt: ")

    def test_rev_list_prints_values(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)
        Commit(2, amend=False).run(repo)

        output = capture_output(RevList(HeadRef(), limit=2), repo)

        self.assertEqual(output, "2\n1\n")

    def test_rev_list_range_prints_range_values(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)
        Commit(2, amend=False).run(repo)
        Commit(3, amend=False).run(repo)

        output = capture_output(RevListRange(CommitRange(ConstantOffsetRef(HeadRef(), 2), HeadRef())), repo)

        self.assertEqual(output, "3\n2\n")

    def test_cherry_pick_range_replays_oldest_to_newest(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)
        Commit(2, amend=False).run(repo)
        Commit(3, amend=False).run(repo)

        CherryPickRange(CommitRange(ConstantOffsetRef(HeadRef(), 3), HeadRef())).run(repo)

        self.assertEqual(values_from_head(repo)[:3], [3, 2, 1])

    def test_cherry_pick_range_can_reduce_with_strategy(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)
        Commit(2, amend=False).run(repo)
        Commit(3, amend=False).run(repo)
        Commit(5, amend=False).run(repo)

        CherryPickRange(CommitRange(ConstantOffsetRef(HeadRef(), 4), ConstantOffsetRef(HeadRef(), 1)), Operator.ADD).run(repo)

        self.assertEqual(values_from_head(repo)[:3], [11, 8, 6])

    def test_revert_creates_negated_value(self):
        repo = Repo()
        Commit(5, amend=False).run(repo)

        Revert(HeadRef()).run(repo)

        self.assertEqual(values_from_head(repo)[:2], [-5, 5])

    def test_revert_range_replays_newest_to_oldest_as_negated_values(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)
        Commit(2, amend=False).run(repo)
        Commit(3, amend=False).run(repo)

        RevertRange(CommitRange(ConstantOffsetRef(HeadRef(), 3), HeadRef())).run(repo)

        self.assertEqual(values_from_head(repo)[:3], [-1, -2, -3])

    def test_delete_branches_removes_named_branches(self):
        repo = Repo()
        Branch("left").run(repo)
        Branch("right").run(repo)

        DeleteBranches(["left", "right"]).run(repo)

        self.assertNotIn("left", repo.branches)
        self.assertNotIn("right", repo.branches)

    def test_list_branches_prints_visible_branches(self):
        repo = Repo()
        Branch("feature").run(repo)
        Checkout("feature").run(repo)
        Branch("earlier").run(repo) # should be sorted before feature (alphabetical)
        Checkout("earlier").run(repo)

        output = capture_output(ListBranches(), repo)

        self.assertEqual(output, "   main!\n * earlier\n   feature\n")

    def test_delete_tags_removes_named_tags(self):
        repo = Repo()
        Tag("old").run(repo)

        DeleteTags(["old"]).run(repo)

        self.assertNotIn("old", repo.tags)

    def test_tag_can_point_at_explicit_ref(self):
        repo = Repo()
        Commit(1, amend=False).run(repo)
        Commit(2, amend=False).run(repo)

        Tag("old", ConstantOffsetRef(HeadRef(), 1)).run(repo)

        self.assertEqual(repo.tags["old"].value, 1)
        self.assertEqual(repo.branches["main"].value, 2)

    def test_conflict_runs_first_block_when_condition_matches(self):
        repo = Repo()
        Checkout("a", create_at=HeadRef()).run(repo)
        Commit(4, amend=False).run(repo)
        Checkout("b", create_at=HeadRef()).run(repo)
        Commit(2, amend=False).run(repo)

        Conflict(
            BranchRef("a"),
            BranchRef("b"),
            [Checkout("a"), Commit(1, amend=False)],
            [Checkout("b"), Commit(2, amend=False)],
            Condition.GT,
        ).run(repo)

        self.assertEqual(repo.branches["a"].value, 1)
        self.assertEqual(repo.branches["b"].value, 2)
        self.assertEqual(repo.HEAD, "a")

    def test_conflict_continue_repeats_and_abort_exits(self):
        repo = Repo()
        Checkout("counter", create_at=HeadRef()).run(repo)
        Commit(2, amend=False).run(repo)
        Checkout("one", create_at=HeadRef()).run(repo)
        Commit(1, amend=False).run(repo)
        Checkout("main").run(repo)

        Conflict(
            BranchRef("counter"),
            BranchRef("main"),
            [
                Checkout("counter"),
                CherryPick(BranchRef("one"), Operator.SUBTRACT),
                MergeContinue(),
            ],
            [MergeAbort()],
            Condition.GT,
        ).run(repo)

        self.assertEqual(repo.branches["counter"].value, 0)

    def test_labeled_continue_can_repeat_outer_conflict(self):
        repo = Repo()
        Checkout("counter", create_at=HeadRef()).run(repo)
        Commit(2, amend=False).run(repo)
        Checkout("one", create_at=HeadRef()).run(repo)
        Commit(1, amend=False).run(repo)
        Checkout("main").run(repo)

        inner = Conflict(
            BranchRef("main"),
            BranchRef("main"),
            [
                Checkout("counter"),
                CherryPick(BranchRef("one"), Operator.SUBTRACT),
                MergeContinue("outer"),
            ],
            [MergeAbort()],
            Condition.IS,
            label="inner",
        )

        Conflict(
            BranchRef("counter"),
            BranchRef("main"),
            [inner],
            [MergeAbort()],
            Condition.GT,
            label="outer",
        ).run(repo)

        self.assertEqual(repo.branches["counter"].value, 0)

    def test_labeled_abort_can_exit_outer_conflict(self):
        repo = Repo()
        Checkout("counter", create_at=HeadRef()).run(repo)
        Commit(2, amend=False).run(repo)
        Checkout("main").run(repo)

        inner = Conflict(
            BranchRef("main"),
            BranchRef("main"),
            [MergeAbort("outer")],
            [Commit(9, amend=False)],
            Condition.IS,
            label="inner",
        )

        Conflict(
            BranchRef("counter"),
            BranchRef("main"),
            [inner, Commit(8, amend=False)],
            [Commit(7, amend=False)],
            Condition.GT,
            label="outer",
        ).run(repo)

        self.assertEqual(repo.branches["counter"].value, 2)
        self.assertEqual(repo.branches["main"].value, 0)


if __name__ == "__main__":
    unittest.main()
