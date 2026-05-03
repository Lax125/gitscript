import unittest

from gitscript.commit_range import CommitRange
from gitscript.refs import BranchRef, ConstantOffsetRef, DynamicOffsetRef, HeadRef
from gitscript.operators import Operator
from gitscript.parser import IncompleteInput, ParseError, parse, parse_repl
from gitscript.statements import (
    Branch,
    Checkout,
    CherryPickRange,
    Commit,
    CommitString,
    Conflict,
    DeleteBranches,
    DeleteTags,
    Log,
    LogRange,
    Merge,
    Revert,
    RevertRange,
    RevList,
    RevListRange,
    Show,
)


class ParserTests(unittest.TestCase):
    def test_parse_basic_commands(self):
        statements = parse(
            """
            git commit   # input integer
            git commit --amend -m 42
            git commit -m "Hello, World!"
            git checkout -b feature
            git merge main -s=-
            git show
            git log HEAD~1
            """
        )

        self.assertIsInstance(statements[0], Commit)
        self.assertIsNone(statements[0].value)
        self.assertFalse(statements[0].amend)

        self.assertIsInstance(statements[1], Commit)
        self.assertEqual(statements[1].value, 42)
        self.assertTrue(statements[1].amend)

        self.assertIsInstance(statements[2], CommitString)
        self.assertEqual(statements[2].value, "Hello, World!")

        self.assertIsInstance(statements[3], Checkout)
        self.assertEqual(statements[3].branch_name, "feature")
        self.assertIsInstance(statements[3].create_at, HeadRef)

        self.assertIsInstance(statements[4], Merge)
        self.assertIsInstance(statements[4].ref, BranchRef)
        self.assertEqual(statements[4].ref.name, "main")
        self.assertEqual(statements[4].op, Operator.SUBTRACT)

        self.assertIsInstance(statements[5], Show)
        self.assertIsInstance(statements[5].ref, HeadRef)

        self.assertIsInstance(statements[6], Log)
        self.assertIsInstance(statements[6].ref, ConstantOffsetRef)

    def test_parse_string_input_commit(self):
        statements = parse('git commit -m "\n')

        self.assertIsInstance(statements[0], CommitString)
        self.assertIsNone(statements[0].value)

    def test_commit_message_option_accepts_space_and_equals_forms(self):
        statements = parse(
            """
            git commit -m 42
            git commit -m=43
            git commit -m "forty four"
            git commit -m="forty five"
            """
        )

        self.assertIsInstance(statements[0], Commit)
        self.assertEqual(statements[0].value, 42)
        self.assertIsInstance(statements[1], Commit)
        self.assertEqual(statements[1].value, 43)
        self.assertIsInstance(statements[2], CommitString)
        self.assertEqual(statements[2].value, "forty four")
        self.assertIsInstance(statements[3], CommitString)
        self.assertEqual(statements[3].value, "forty five")

    def test_quoted_numeric_commit_message_is_a_string(self):
        statements = parse('git commit -m "42"')

        self.assertIsInstance(statements[0], CommitString)
        self.assertEqual(statements[0].value, "42")

    def test_merge_strategy_option_accepts_space_and_equals_forms(self):
        statements = parse(
            """
            git merge main -s -
            git merge main -s=-
            """
        )

        self.assertIsInstance(statements[0], Merge)
        self.assertEqual(statements[0].op, Operator.SUBTRACT)
        self.assertIsInstance(statements[1], Merge)
        self.assertEqual(statements[1].op, Operator.SUBTRACT)

    def test_parse_conflict_block(self):
        statements = parse(
            """
            <<<<<<< a
                git checkout a
                git merge b -s=-
            =======
                git checkout b
                git merge a -s=-
            >>>>>>> b
            """
        )

        self.assertEqual(len(statements), 1)
        conflict = statements[0]
        self.assertIsInstance(conflict, Conflict)
        self.assertIsInstance(conflict.ref_a, BranchRef)
        self.assertEqual(conflict.ref_a.name, "a")
        self.assertEqual(len(conflict.block_a), 2)
        self.assertEqual(len(conflict.block_b), 2)
        self.assertIsInstance(conflict.ref_b, BranchRef)
        self.assertEqual(conflict.ref_b.name, "b")

    def test_parse_branch_delete_and_create_at_ref(self):
        statements = parse(
            """
            git branch saved HEAD~1
            git branch -d stale old
            git checkout -b feature HEAD~2
            """
        )

        self.assertIsInstance(statements[0], Branch)
        self.assertEqual(statements[0].branch_name, "saved")
        self.assertIsInstance(statements[0].ref, ConstantOffsetRef)
        self.assertIsInstance(statements[1], DeleteBranches)
        self.assertEqual(statements[1].branch_names, ["stale", "old"])
        self.assertIsInstance(statements[2], Checkout)
        self.assertEqual(statements[2].branch_name, "feature")
        self.assertIsInstance(statements[2].create_at, ConstantOffsetRef)

    def test_parse_tag_delete(self):
        statements = parse("git tag -d v1 v2")

        self.assertIsInstance(statements[0], DeleteTags)
        self.assertEqual(statements[0].tag_names, ["v1", "v2"])

    def test_parse_range_commands(self):
        statements = parse(
            """
            git cherry-pick HEAD~2..HEAD
            git revert HEAD
            git revert HEAD~2..HEAD
            git log -n 2 --reverse HEAD~2..HEAD
            git rev-list -n=3 HEAD
            git rev-list --reverse HEAD~2..HEAD
            """
        )

        self.assertIsInstance(statements[0], CherryPickRange)
        self.assertIsInstance(statements[0].range, CommitRange)
        self.assertIsInstance(statements[1], Revert)
        self.assertIsInstance(statements[2], RevertRange)
        self.assertIsInstance(statements[2].range, CommitRange)
        self.assertIsInstance(statements[3], LogRange)
        self.assertEqual(statements[3].limit, 2)
        self.assertTrue(statements[3].reverse)
        self.assertIsInstance(statements[4], RevList)
        self.assertEqual(statements[4].limit, 3)
        self.assertIsInstance(statements[5], RevListRange)
        self.assertTrue(statements[5].reverse)

    def test_parse_log_ref_options(self):
        statements = parse("git log --reverse -n 1 HEAD")

        self.assertIsInstance(statements[0], Log)
        self.assertEqual(statements[0].limit, 1)
        self.assertTrue(statements[0].reverse)

    def test_refs_associate_right_to_left(self):
        statements = parse("git show HEAD~foo~1")
        ref = statements[0].ref

        self.assertIsInstance(ref, DynamicOffsetRef)
        self.assertIsInstance(ref.base, HeadRef)
        self.assertIsInstance(ref.offset_expr, ConstantOffsetRef)
        self.assertIsInstance(ref.offset_expr.base, BranchRef)
        self.assertEqual(ref.offset_expr.base.name, "foo")
        self.assertEqual(ref.offset_expr.offset_value, 1)

    def test_parse_reports_line_number(self):
        with self.assertRaisesRegex(ParseError, "Line 3"):
            parse("\n\ngit nope")

    def test_repl_parse_reports_incomplete_conflict_blocks(self):
        with self.assertRaises(IncompleteInput):
            parse_repl("<<<<<<< a\n    git checkout a\n")

        with self.assertRaises(ParseError):
            parse("<<<<<<< a\n    git checkout a\n")

    def test_repl_parse_accepts_complete_single_statement(self):
        statements = parse_repl("git commit -m 5")

        self.assertEqual(len(statements), 1)
        self.assertIsInstance(statements[0], Commit)
        self.assertEqual(statements[0].value, 5)


if __name__ == "__main__":
    unittest.main()
