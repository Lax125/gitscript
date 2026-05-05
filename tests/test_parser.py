import unittest

from gitscript.commit_range import CommitRange
from gitscript.refs import BranchRef, ConstantOffsetRef, DynamicOffsetRef, HeadRef
from gitscript.operators import Condition, Operator
from gitscript.parser import IncompleteInput, ParseError, parse, parse_repl
from gitscript.statements import (
    Branch,
    Checkout,
    CherryPickRange,
    CherryPick,
    Commit,
    CommitString,
    Config,
    AliasCall,
    Conflict,
    DefineAlias,
    DefineFunction,
    DeleteBranches,
    DeleteTags,
    Exit,
    ListBranches,
    Log,
    LogRange,
    MergeAbort,
    MergeContinue,
    Revert,
    RevertRange,
    RevList,
    RevListRange,
    Rescue,
    Sequence,
    Show,
    StatementBlock,
)


class ParserTests(unittest.TestCase):
    def test_parse_basic_commands(self):
        statements = parse(
            """
            git commit   # input integer
            git commit --amend 42
            git commit -m "Hello, World!"
            git checkout -b feature
            git cherry-pick main -s=sub
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

        self.assertIsInstance(statements[4], CherryPick)
        self.assertIsInstance(statements[4].ref, BranchRef)
        self.assertEqual(statements[4].ref.name, "main")
        self.assertEqual(statements[4].op, Operator.SUBTRACT)

        self.assertIsInstance(statements[5], Show)
        self.assertIsInstance(statements[5].ref, HeadRef)

        self.assertIsInstance(statements[6], Log)
        self.assertIsInstance(statements[6].ref, ConstantOffsetRef)

    def test_parse_string_input_commit(self):
        statements = parse("git commit -m\n")

        self.assertIsInstance(statements[0], CommitString)
        self.assertIsNone(statements[0].value)

    def test_parse_triple_quoted_commit_strings(self):
        statements = parse(
            'git commit -m """this is a\n'
            'multiline string and " does not need to be escaped\n'
            '""" # trailing newline is included\n'
            'git commit -m """no trailing newline"""'
        )

        self.assertIsInstance(statements[0], CommitString)
        self.assertEqual(
            statements[0].value,
            'this is a\nmultiline string and " does not need to be escaped\n',
        )
        self.assertIsInstance(statements[1], CommitString)
        self.assertEqual(statements[1].value, "no trailing newline")

    def test_commit_accepts_integer_and_string_forms(self):
        statements = parse(
            "git commit 42\n"
            "git commit true\n"
            'git commit -m "forty four"\n'
            'git commit -m="forty five"\n'
            'git commit -m="""equals form"""\n'
            "git commit -m\n"
        )

        self.assertIsInstance(statements[0], Commit)
        self.assertEqual(statements[0].value, 42)
        self.assertIsInstance(statements[1], Commit)
        self.assertEqual(statements[1].value, 1)
        self.assertIsInstance(statements[2], CommitString)
        self.assertEqual(statements[2].value, "forty four")
        self.assertIsInstance(statements[3], CommitString)
        self.assertEqual(statements[3].value, "forty five")
        self.assertIsInstance(statements[4], CommitString)
        self.assertEqual(statements[4].value, "equals form")
        self.assertIsInstance(statements[5], CommitString)
        self.assertIsNone(statements[5].value)

    def test_quoted_numeric_commit_message_is_a_string(self):
        statements = parse('git commit -m "42"')

        self.assertIsInstance(statements[0], CommitString)
        self.assertEqual(statements[0].value, "42")

        single_quoted_numeric = parse("git commit -m '42'")
        self.assertIsInstance(single_quoted_numeric[0], CommitString)
        self.assertEqual(single_quoted_numeric[0].value, "42")

        single_quoted_text = parse("git commit -m 'forty two'")
        self.assertIsInstance(single_quoted_text[0], CommitString)
        self.assertEqual(single_quoted_text[0].value, "forty two")

    def test_cherry_pick_strategy_option_accepts_space_and_equals_forms(self):
        statements = parse(
            """
            git cherry-pick main -s sub
            git cherry-pick main -s=sub
            git cherry-pick main -s min
            git cherry-pick main -s=max
            """
        )

        self.assertIsInstance(statements[0], CherryPick)
        self.assertEqual(statements[0].op, Operator.SUBTRACT)
        self.assertIsInstance(statements[1], CherryPick)
        self.assertEqual(statements[1].op, Operator.SUBTRACT)
        self.assertIsInstance(statements[2], CherryPick)
        self.assertEqual(statements[2].op, Operator.MIN)
        self.assertIsInstance(statements[3], CherryPick)
        self.assertEqual(statements[3].op, Operator.MAX)

    def test_parse_config(self):
        statements = parse(
            """
            git config commit.verbose true
            git config commit.verbose 0
            git config commit.verbose 2
            git config merge.verbosity 0
            git config merge.verbosity 1
            git config merge.verbosity 2
            """
        )

        self.assertIsInstance(statements[0], Config)
        self.assertEqual(statements[0].key, "commit.verbose")
        self.assertEqual(statements[0].value, 1)
        self.assertEqual(statements[1].value, 0)
        self.assertEqual(statements[2].value, 2)
        self.assertEqual(statements[3].value, 0)
        self.assertEqual(statements[4].value, 1)
        self.assertEqual(statements[5].value, 2)

    def test_config_rejects_unknown_keys_and_values(self):
        invalid_sources = [
            "git config commit.verbose yes",
            "git config merge.verbosity 3",
            "git config merge.verbosity nope",
            "git config branch.verbose true",
            "git config commit.verbose",
        ]

        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(ParseError):
                    parse(source)

    def test_parse_statement_separator_aliases_functions_and_exit(self):
        statements = parse(
            """
            git commit true && git commit false
            git config alias.cp 'cherry-pick'
            git config alias.pick -l label -b target -p owner -t mark -r source -o strategy '!
                git cherry-pick $source -s=$strategy && exit
            '
            git later new-label other main saved main max
            exit
            """
        )

        self.assertEqual(len(statements), 5)
        self.assertIsInstance(statements[0], Sequence)
        self.assertIsInstance(statements[0].left, Commit)
        self.assertEqual(statements[0].left.value, 1)
        self.assertIsInstance(statements[0].right, Commit)
        self.assertEqual(statements[0].right.value, 0)
        self.assertIsInstance(statements[1], DefineAlias)
        self.assertEqual(statements[1].name, "cp")
        self.assertEqual(statements[1].fragment, "cherry-pick")
        self.assertIsInstance(statements[2], DefineFunction)
        self.assertEqual(
            [(parameter.kind, parameter.name) for parameter in statements[2].parameters],
            [
                ("-l", "label"),
                ("-b", "target"),
                ("-p", "owner"),
                ("-t", "mark"),
                ("-r", "source"),
                ("-o", "strategy"),
            ],
        )
        self.assertIsInstance(statements[3], AliasCall)
        self.assertEqual(statements[3].name, "later")
        self.assertEqual(statements[3].args, ["new-label", "other", "main", "saved", "main", "max"])
        self.assertIsInstance(statements[4], Exit)

    def test_parse_statement_composition_precedence_and_anonymous_blocks(self):
        statements = parse(
            """
            git commit 1 && git commit 2 || git commit 3 && '!git commit 4 && git commit 5'
            """
        )

        self.assertEqual(len(statements), 1)
        self.assertIsInstance(statements[0], Rescue)
        self.assertIsInstance(statements[0].left, Sequence)
        self.assertIsInstance(statements[0].right, Sequence)
        self.assertIsInstance(statements[0].right.right, StatementBlock)

    def test_parse_nested_anonymous_blocks_with_apostrophes_in_strings(self):
        statements = parse("'!git commit -m \"don't\" && '!git commit 2''")

        self.assertEqual(len(statements), 1)
        self.assertIsInstance(statements[0], StatementBlock)
        self.assertIsInstance(statements[0].statements[0], Sequence)
        self.assertIsInstance(statements[0].statements[0].left, CommitString)
        self.assertEqual(statements[0].statements[0].left.value, "don't")
        self.assertIsInstance(statements[0].statements[0].right, StatementBlock)

    def test_parse_conflict_block(self):
        statements = parse(
            """
            git merge -s gt
            <<<<<<< a
                git checkout a
                git cherry-pick b -s=sub
                git merge --continue
            =======
                git checkout b
                git merge --abort
            >>>>>>> b
            """
        )

        self.assertEqual(len(statements), 1)
        conflict = statements[0]
        self.assertIsInstance(conflict, Conflict)
        self.assertIsInstance(conflict.ref_a, BranchRef)
        self.assertEqual(conflict.ref_a.name, "a")
        self.assertEqual(conflict.condition, Condition.GT)
        self.assertEqual(len(conflict.block_a), 3)
        self.assertEqual(len(conflict.block_b), 2)
        self.assertIsInstance(conflict.ref_b, BranchRef)
        self.assertEqual(conflict.ref_b.name, "b")

    def test_parse_merge_continue_and_abort(self):
        statements = parse(
            """
            git merge -s is loop
            <<<<<<< a
                git merge --continue loop
            =======
                git merge --abort loop
            >>>>>>> b
            """
        )

        conflict = statements[0]
        self.assertEqual(conflict.condition, Condition.IS)
        self.assertEqual(conflict.label, "loop")
        self.assertIsInstance(conflict.block_a[0], MergeContinue)
        self.assertEqual(conflict.block_a[0].label, "loop")
        self.assertIsInstance(conflict.block_b[0], MergeAbort)
        self.assertEqual(conflict.block_b[0].label, "loop")

    def test_parse_unlabeled_merge_continue_and_abort(self):
        statements = parse(
            """
            git merge -s is
            <<<<<<< a
                git merge --continue
            =======
                git merge --abort
            >>>>>>> b
            """
        )

        conflict = statements[0]
        self.assertIsNone(conflict.label)
        self.assertIsNone(conflict.block_a[0].label)
        self.assertIsNone(conflict.block_b[0].label)

    def test_parse_branch_delete_and_create_at_ref(self):
        statements = parse(
            """
            git branch
            git branch saved HEAD~1
            git branch -d stale old
            git checkout -b feature HEAD~2
            """
        )

        self.assertIsInstance(statements[0], ListBranches)
        self.assertIsInstance(statements[1], Branch)
        self.assertEqual(statements[1].branch_name, "saved")
        self.assertIsInstance(statements[1].ref, ConstantOffsetRef)
        self.assertIsInstance(statements[2], DeleteBranches)
        self.assertEqual(statements[2].branch_names, ["stale", "old"])
        self.assertIsInstance(statements[3], Checkout)
        self.assertEqual(statements[3].branch_name, "feature")
        self.assertIsInstance(statements[3].create_at, ConstantOffsetRef)

    def test_branch_and_tag_names_allow_restricted_character_set(self):
        statements = parse(
            """
            git branch feature/path-1_ok
            git checkout -b feature2
            git branch branch3
            git tag tag4
            git branch -d feature/path-1_ok feature2 branch3
            git tag -d tag4
            """
        )

        self.assertEqual(statements[0].branch_name, "feature/path-1_ok")
        self.assertEqual(statements[1].branch_name, "feature2")
        self.assertEqual(statements[2].branch_name, "branch3")
        self.assertEqual(statements[3].tag_name, "tag4")
        self.assertEqual(statements[4].branch_names, ["feature/path-1_ok", "feature2", "branch3"])
        self.assertEqual(statements[5].tag_names, ["tag4"])

    def test_branch_tag_and_ref_names_reject_invalid_names(self):
        invalid_sources = [
            "git branch HEAD",
            "git tag HEAD",
            "git branch git",
            "git tag commit",
            "git checkout -b merge",
            "git branch max",
            "git tag is",
            "git checkout -b -bad",
            "git branch bad.name",
            "git tag bad@name",
            "git checkout bad:name",
            "git show bad.name",
        ]

        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(ParseError):
                    parse(source)

    def test_parse_tag_delete(self):
        statements = parse("git tag -d v1 v2")

        self.assertIsInstance(statements[0], DeleteTags)
        self.assertEqual(statements[0].tag_names, ["v1", "v2"])

    def test_parse_range_commands(self):
        statements = parse(
            """
            git cherry-pick HEAD~2..HEAD
            git cherry-pick HEAD~2..HEAD -s add
            git revert HEAD
            git revert HEAD~2..HEAD
            git log -n 2 --reverse --oneline HEAD~2..HEAD
            git rev-list -n=3 HEAD
            git rev-list --reverse HEAD~2..HEAD
            """
        )

        self.assertIsInstance(statements[0], CherryPickRange)
        self.assertIsInstance(statements[0].range, CommitRange)
        self.assertEqual(statements[0].op, Operator.THEIRS)
        self.assertIsInstance(statements[1], CherryPickRange)
        self.assertEqual(statements[1].op, Operator.ADD)
        self.assertIsInstance(statements[2], Revert)
        self.assertIsInstance(statements[3], RevertRange)
        self.assertIsInstance(statements[3].range, CommitRange)
        self.assertIsInstance(statements[4], LogRange)
        self.assertEqual(statements[4].limit, 2)
        self.assertTrue(statements[4].reverse)
        self.assertTrue(statements[4].oneline)
        self.assertIsInstance(statements[5], RevList)
        self.assertEqual(statements[5].limit, 3)
        self.assertIsInstance(statements[6], RevListRange)
        self.assertTrue(statements[6].reverse)

    def test_parse_log_ref_options(self):
        statements = parse("git log --reverse --oneline -n 1 HEAD")

        self.assertIsInstance(statements[0], Log)
        self.assertEqual(statements[0].limit, 1)
        self.assertTrue(statements[0].reverse)
        self.assertTrue(statements[0].oneline)

        with self.assertRaises(ParseError):
            parse("git rev-list --oneline HEAD")

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
            parse("\n\ngit branch bad.name")

    def test_repl_parse_reports_incomplete_conflict_blocks(self):
        with self.assertRaises(IncompleteInput):
            parse_repl("git merge\n<<<<<<< a\n    git checkout a\n")

        with self.assertRaises(ParseError):
            parse("<<<<<<< a\n    git checkout a\n")

        with self.assertRaises(IncompleteInput):
            parse_repl('git commit -m """unfinished\nstring')

        with self.assertRaises(ParseError):
            parse('git commit -m """unfinished\nstring')

    def test_repl_parse_accepts_complete_single_statement(self):
        statements = parse_repl("git commit 5")

        self.assertEqual(len(statements), 1)
        self.assertIsInstance(statements[0], Commit)
        self.assertEqual(statements[0].value, 5)


if __name__ == "__main__":
    unittest.main()
