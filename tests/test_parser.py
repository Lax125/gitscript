import unittest

from gitscript.ast import BranchRef, ConstantOffsetRef, DynamicOffsetRef, HeadRef
from gitscript.operators import Operator
from gitscript.parser import ParseError, parse
from gitscript.statements import Checkout, Commit, CommitString, Conflict, Log, Merge, Show


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
        self.assertTrue(statements[3].create_branch)

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

    def test_quoted_numeric_commit_message_is_a_string(self):
        statements = parse('git commit -m "42"')

        self.assertIsInstance(statements[0], CommitString)
        self.assertEqual(statements[0].value, "42")

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


if __name__ == "__main__":
    unittest.main()
