import unittest

from gitscript.parser import ParseError, parse
from utils import run_program


class ProgramTests(unittest.TestCase):
    def test_comments_blank_lines_and_string_escaping(self):
        repo, output = run_program(
            r'''
            # Full-line comments and blank lines are ignored.

            git tag root
            git commit -m "A#B \"C\" \\ D"  # Inline comments are ignored outside quotes.
            git log root..HEAD
            '''
        )

        self.assertEqual(output, 'A#B "C" \\ D\n')
        self.assertEqual(repo.branches["main"].value, ord("A"))

    def test_integer_commit_input_amend_show_and_reset(self):
        repo, output = run_program(
            """
            git commit
            git commit --amend -m 8
            git show
            git reset HEAD~1
            git show
            """,
            inputs=["5"],
        )

        self.assertEqual(output, "8\n0\n")
        self.assertEqual(repo.branches["main"].value, 0)

    def test_string_input_commit_and_null_characters_are_printed(self):
        repo, output = run_program(
            'git tag root\n'
            'git commit -m "\n'
            'git log root..HEAD\n'
            'git commit -m 0\n'
            'git log -n 1\n',
            inputs=["Yo"],
        )

        self.assertEqual(output, "Yo\n\x00\n")
        self.assertEqual(repo.branches["main"].value, 0)

    def test_string_commits_do_not_allow_amend(self):
        with self.assertRaises(ParseError):
            parse('git commit --amend -m "unsafe"')

        with self.assertRaises(ParseError):
            parse('git commit --amend -m "\n')

    def test_hello_world_readme_example(self):
        repo, output = run_program(
            """
            git tag root
            git commit -m "Hello, World!"
            git log root..HEAD
            """
        )

        self.assertEqual(output, "Hello, World!\n")
        self.assertEqual(repo.branches["main"].value, ord("H"))

    def test_branch_tag_checkout_create_at_and_delete(self):
        repo, output = run_program(
            """
            git commit -m 1
            git commit -m 2
            git branch one HEAD~1
            git checkout -b two one
            git show
            git checkout main
            git branch temp
            git branch -d temp
            git branch temp
            git tag saved
            git tag -d saved
            git tag saved
            git show saved
            """
        )

        self.assertEqual(output, "1\n2\n")
        self.assertEqual(repo.branches["one"].value, 1)
        self.assertEqual(repo.branches["two"].value, 1)
        self.assertIn("temp", repo.branches)
        self.assertEqual(repo.tags["saved"].value, 2)

    def test_all_cherry_pick_strategies(self):
        repo, output = run_program(
            """
            git commit -m 10
            git branch ten
            git commit -m 3
            git cherry-pick ten -s=+
            git show
            git reset HEAD~1
            git cherry-pick ten -s=-
            git show
            git reset HEAD~1
            git cherry-pick ten -s=*
            git show
            git reset HEAD~1
            git cherry-pick ten -s=/
            git show
            git reset HEAD~1
            git cherry-pick ten -s=%
            git show
            git reset HEAD~1
            git cherry-pick ten -s=>
            git show
            git reset HEAD~1
            git cherry-pick ten -s=<
            git show
            git reset HEAD~1
            git cherry-pick ten -s=>=
            git show
            git reset HEAD~1
            git cherry-pick ten -s=<=
            git show
            git reset HEAD~1
            git cherry-pick ten -s===
            git show
            git reset HEAD~1
            git cherry-pick ten -s=!=
            git show
            git reset HEAD~1
            git cherry-pick ten
            git show
            git reset HEAD~1
            git cherry-pick ten -s=ours
            git show
            """
        )

        self.assertEqual(output, "13\n-7\n30\n0\n3\n0\n1\n0\n1\n0\n1\n10\n3\n")
        self.assertEqual(repo.branches["main"].value, 3)

    def test_commit_refs_static_dynamic_parenthesized_and_missing_ancestor(self):
        repo, output = run_program(
            """
            git commit -m 65
            git commit -m 66
            git branch data
            git commit -m 1
            git branch offset
            git show data~1
            git show data~(offset)
            """
        )

        self.assertEqual(output, "65\n65\n")
        self.assertEqual(repo.branches["offset"].value, 1)

        with self.assertRaisesRegex(RuntimeError, "Ancestor does not exist"):
            run_program("git commit -m 1\ngit show HEAD~2\n")

    def test_commit_ranges_log_and_rev_list(self):
        repo, output = run_program(
            """
            git commit -m 65
            git commit -m 66
            git commit -m 0
            git log HEAD~3..HEAD
            git log --reverse -n 2 HEAD
            git rev-list -n=3 HEAD
            git rev-list --reverse HEAD~3..HEAD
            git rev-list HEAD..HEAD
            """
        )

        self.assertEqual(output, "\x00BA\nB\x00\n0\n66\n65\n65\n66\n0\n")
        self.assertEqual(repo.branches["main"].value, 0)

    def test_cherry_pick_and_revert_ref_and_range(self):
        repo, output = run_program(
            """
            git commit -m 1
            git commit -m 2
            git branch two
            git commit -m 3
            git cherry-pick two
            git rev-list -n 1
            git revert two
            git rev-list -n 1
            git cherry-pick HEAD~5..HEAD~3
            git rev-list -n 2
            git reset HEAD~2
            git cherry-pick HEAD~5..HEAD~3 -s +
            git rev-list -n 2
            git revert HEAD~7..HEAD~5
            git rev-list -n 2
            """
        )

        self.assertEqual(output, "2\n-2\n2\n1\n1\n-1\n-1\n-2\n")
        self.assertEqual(repo.branches["main"].value, -1)

    def test_rebase_replays_current_branch_onto_target(self):
        repo, output = run_program(
            """
            git commit -m 1
            git checkout -b feature
            git commit -m 2
            git commit -m 3
            git checkout main
            git commit -m 9
            git checkout feature
            git rebase main
            git rev-list -n 5
            """
        )

        self.assertEqual(output, "3\n2\n9\n1\n0\n")
        self.assertEqual(repo.branches["feature"].parent.parent, repo.branches["main"])

    def test_merge_conflict_if_else_continue_and_abort(self):
        repo, output = run_program(
            """
            git checkout -b counter
            git commit -m 3
            git checkout -b one
            git commit -m 1

            git checkout main

            git merge -s >
            <<<<<<< counter
                git checkout counter
                git cherry-pick one -s=-
                git merge --continue
            =======
                git merge --abort
            >>>>>>> main

            git show counter

            git checkout main
            git commit -m 9
            git branch same
            git merge -s is
            <<<<<<< main
                git commit -m 1
            =======
                git commit -m 2
            >>>>>>> same

            git show
            """
        )

        self.assertEqual(output, "0\n1\n")
        self.assertEqual(repo.branches["counter"].value, 0)
        self.assertEqual(repo.branches["main"].value, 1)


if __name__ == "__main__":
    unittest.main()
