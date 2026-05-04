import unittest

from gitscript.parser import ParseError, parse
from utils import run_program, run_program_with_debug


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

    def test_triple_quoted_multiline_strings(self):
        repo, output = run_program(
            '''\
git tag root
git commit -m """this is a
multiline string and " does not need to be escaped
""" # trailing newline is included
git log root..HEAD
git commit -m """no trailing newline"""
git log HEAD~19..HEAD
'''
        )

        self.assertEqual(
            output,
            'this is a\nmultiline string and " does not need to be escaped\n\n'
            "no trailing newline\n",
        )
        self.assertEqual(repo.branches["main"].value, ord("n"))

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

        with self.assertRaises(ParseError):
            parse('git commit --amend -m """unsafe"""')

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

    def test_branch_without_arguments_lists_global_branches(self):
        repo, output = run_program(
            """
            git checkout -b feature
            git branch
            """
        )

        self.assertEqual(output, "   main !\n * feature\n")
        self.assertEqual(repo.HEAD, "feature")

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
            git reset HEAD~1
            git cherry-pick ten -s=min
            git show
            git reset HEAD~1
            git cherry-pick ten -s=max
            git show
            git reset HEAD~1
            """
        )

        self.assertEqual(output, "13\n-7\n30\n0\n3\n0\n1\n0\n1\n0\n1\n10\n3\n3\n10\n")
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
            git reset HEAD~2
            git cherry-pick HEAD~5..HEAD~3 -s max
            git rev-list -n 2
            git revert HEAD~7..HEAD~5
            git rev-list -n 2
            """
        )

        self.assertEqual(output, "2\n-2\n2\n1\n1\n-1\n2\n1\n-1\n-2\n")
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

    def test_labeled_merge_continue_and_abort_target_outer_conflicts(self):
        repo, output = run_program(
            """
            git checkout -b counter
            git commit -m 2
            git checkout -b one
            git commit -m 1
            git checkout main

            git merge -s > loop
            <<<<<<< counter
                git merge -s is inner
                <<<<<<< main
                    git checkout counter
                    git cherry-pick one -s=-
                    git merge --continue loop
                =======
                    git merge --abort
                >>>>>>> main
            =======
                git merge --abort
            >>>>>>> main

            git show counter

            git merge -s > exit
            <<<<<<< counter
                git merge --abort
            =======
                git merge -s is inner
                <<<<<<< main
                    git merge --abort exit
                =======
                    git commit -m 9
                >>>>>>> main
                git commit -m 8
            >>>>>>> counter

            git show main
            """
        )

        self.assertEqual(output, "0\n0\n")
        self.assertEqual(repo.branches["counter"].value, 0)
        self.assertEqual(repo.branches["main"].value, 0)

    def test_commit_verbose_logs_commit_creation_to_debug_output(self):
        repo, output, debug = run_program_with_debug(
            """
            git config commit.verbose 2
            git tag root
            git commit -m 1
            git commit --amend -m 2
            git commit -m "Hi"
            git branch base
            git cherry-pick base
            git cherry-pick root..base
            git revert base
            git revert root..base
            git checkout -b feature root
            git commit -m 7
            git rebase main
            git config commit.verbose false
            git commit -m 99
            """
        )

        self.assertEqual(output, "")
        self.assertIn("[commit] branch=main value=1 parent=0 operation=git commit", debug)
        self.assertIn("[commit] branch=main value=2 parent=0 operation=git commit", debug)
        self.assertIn("operation=git commit string", debug)
        self.assertIn("operation=git cherry-pick", debug)
        self.assertIn("operation=git cherry-pick range", debug)
        self.assertIn("operation=git revert", debug)
        self.assertIn("operation=git revert range", debug)
        self.assertIn("[commit] branch=feature value=7 parent=0 operation=git commit", debug)
        self.assertIn("operation=git rebase", debug)
        self.assertNotIn("value=99", debug)
        self.assertEqual(repo.branches["feature"].value, 99)

    def test_merge_verbosity_logs_merge_debug_output(self):
        repo, output, debug = run_program_with_debug(
            """
            git checkout -b counter
            git commit -m 1
            git checkout -b one
            git commit -m 1
            git checkout main

            git config merge.verbosity 2
            git merge -s > loop
            <<<<<<< counter
                git checkout counter
                git cherry-pick one -s=-
                git merge --continue loop
            =======
                git merge --abort loop
            >>>>>>> main

            git config merge.verbosity 0
            git checkout main
            git merge -s ==
            <<<<<<< main
                git commit -m 9
            =======
                git commit -m 8
            >>>>>>> counter

            git show counter
            """
        )

        self.assertEqual(output, "0\n")
        self.assertIn("[merge] begin label=loop condition=>", debug)
        self.assertIn("[merge] check label=loop condition=> left=1 right=0 selected=top", debug)
        self.assertIn("[merge] continue target=loop handled_by=loop", debug)
        self.assertIn("[merge] check label=loop condition=> left=0 right=0 selected=bottom", debug)
        self.assertIn("[merge] abort target=loop handled_by=loop", debug)
        self.assertNotIn("condition==", debug)
        self.assertEqual(repo.branches["counter"].value, 0)

    def test_statement_separator_and_true_false_integer_literals(self):
        repo, output = run_program(
            """
            git commit -m true && git commit -m false && git rev-list -n 2
            """
        )

        self.assertEqual(output, "0\n1\n")
        self.assertEqual(repo.branches["main"].value, 0)

    def test_statement_separator_treats_merge_conflict_as_one_statement(self):
        repo, output = run_program(
            """
            git checkout -b counter
            git commit -m 1
            git checkout main
            git merge -s >
            <<<<<<< counter
                git merge --abort
            =======
                git commit -m 9
            >>>>>>> main
            git show counter
            """
        )

        self.assertEqual(output, "1\n")
        self.assertEqual(repo.branches["counter"].value, 1)

        invalid_sources = [
            """
            git merge
            <<<<<<< counter && git show
            =======
            >>>>>>> main
            """,
            """
            git merge
            <<<<<<< counter
            ======= && git show
            >>>>>>> main
            """,
            """
            git merge
            <<<<<<< counter
            =======
            >>>>>>> main && git show
            """,
        ]
        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(ParseError):
                    parse(source)

    def test_shortform_aliases_support_repeated_substitution(self):
        repo, output = run_program(
            """
            git config alias.c 'commit -m'
            git config alias.cm 'c'
            git cm 5
            git show
            """
        )

        self.assertEqual(output, "5\n")
        self.assertEqual(repo.branches["main"].value, 5)

    def test_shortform_expansion_must_be_exactly_one_statement(self):
        repo, output = run_program("git config alias.twice 'commit -m 20 && git show'\n")

        self.assertEqual(output, "")
        self.assertIn("twice", repo.aliases)

        with self.assertRaisesRegex(RuntimeError, "exactly one statement"):
            run_program(
                """
                git config alias.twice 'commit -m 20 && git show'
                git twice
                """
            )

    def test_shortform_expansion_can_define_alias_function_and_multiline_string(self):
        repo, output = run_program(
            '''\
git config alias.make-short "config alias.c 'commit -m'"
git make-short
git c 12
git config alias.make-function "config alias.bump '!git commit -m 3'"
git make-function
git bump
git config alias.say 'commit -m'
git say """A
B"""
git log HEAD~3..HEAD
'''
        )

        self.assertEqual(output, "A\nB\n")
        self.assertEqual(repo.branches["main"].value, ord("A"))

    def test_function_bodies_are_validated_when_defined(self):
        invalid_sources = [
            ("git config alias.bad '!wat'\n", "must start with git"),
            ("git config alias.bad '!git cherry-pick main -s nope'\n", "Unknown strategy"),
            (
                "git config alias.bad -s branch_name '!git checkout $branch_name'\n",
                "branch name expects",
            ),
            (
                "git config alias.bad -p target '!git branch -d $target'\n",
                "branch deletion expects",
            ),
        ]

        for source, message in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ParseError, message):
                    run_program(source)

    def test_functions_bind_typed_parameters_on_call_stack(self):
        repo, output = run_program(
            """
            git tag root
            git commit -m 10
            git branch ten
            git checkout -b out root
            git config alias.use -i amount -s text -r source -r root_ref -c condition -o strategy '!
                git checkout main
                git cherry-pick $source -s=$strategy
                git merge -s $condition
                <<<<<<< main
                    git commit -m $amount
                    git commit -m "$text"
                =======
                    git commit -m 0
                >>>>>>> $root_ref
            '
            git use 7 "A" ten root > max
            git rev-list --reverse root..out
            """
        )

        self.assertEqual(output, "10\n7\n65\n")
        self.assertEqual(repo.branches["out"].value, ord("A"))
        self.assertEqual(repo.call_stack, [])

    def test_function_defaults_named_arguments_and_exit(self):
        repo, output = run_program(
            """
            git config alias.make -i amount=1 '!
                git commit -m $amount
                exit
                git commit -m 99
            '
            git make
            git make --amount 4
            git rev-list -n 3
            """
        )

        self.assertEqual(output, "4\n1\n0\n")
        self.assertEqual(repo.branches["main"].value, 4)

    def test_function_local_branches_shadow_globals_and_are_cleaned_up(self):
        repo, output = run_program(
            """
            git branch branch1
            git config alias.localize '!
                git branch branch1
                git checkout branch1
                git commit -m 5
            '
            git localize
            git checkout branch1
            git show
            """
        )

        self.assertEqual(output, "0\n")
        self.assertEqual(repo.branches["branch1"].value, 0)
        self.assertNotIn("branch1", repo.call_stack)

    def test_function_main_alias_modifies_caller_branch_and_restores_head(self):
        repo, output = run_program(
            """
            git checkout -b work
            git commit -m 1
            git config alias.bump '!
                git checkout main
                git commit -m 2
                git branch temp
                exit
                git commit -m 99
            '
            git bump
            git show work
            """
        )

        self.assertEqual(output, "2\n")
        self.assertEqual(repo.branches["work"].value, 2)
        self.assertEqual(repo.HEAD, "work")
        self.assertNotIn("temp", repo.branches)

    def test_function_local_tags_shadow_globals_and_are_cleaned_up(self):
        repo, output = run_program(
            """
            git commit -m 4
            git tag saved
            git commit -m 9
            git config alias.local_tag '!
                git tag saved
                git show saved
            '
            git local_tag
            git show saved
            """
        )

        self.assertEqual(output, "9\n4\n")
        self.assertEqual(repo.tags["saved"].value, 4)

    def test_function_can_use_passed_unprotected_branch_but_not_main_or_current_branch(self):
        repo, output = run_program(
            """
            git commit -m 7
            git branch other
            git reset HEAD~1
            git config alias.peek -b target '!
                git show $target
            '
            git peek other
            """
        )

        self.assertEqual(output, "7\n")

        with self.assertRaisesRegex(RuntimeError, "protected branch"):
            run_program(
                """
                git config alias.peek -b target '!
                    git show $target
                '
                git peek main
                """
            )

        with self.assertRaisesRegex(RuntimeError, "protected branch"):
            run_program(
                """
                git checkout -b work
                git config alias.peek -b target '!
                    git show $target
                '
                git peek work
                """
            )

        with self.assertRaisesRegex(RuntimeError, "does not exist"):
            run_program(
                """
                git config alias.peek -b target '!
                    git show $target
                '
                git peek missing
                """
            )

    def test_label_parameters_require_unused_names_and_create_refs_in_caller_frame(self):
        repo, output = run_program(
            """
            git commit -m 4
            git config alias.make_refs -l branch_name -l tag_name '!
                git branch $branch_name
                git checkout $branch_name
                git commit -m 9
                git tag $tag_name
                git show $tag_name
            '
            git make_refs temp mark
            git show main
            """
        )

        self.assertEqual(output, "9\n4\n")
        self.assertEqual(repo.branches["main"].value, 4)
        self.assertEqual(repo.branches["temp"].value, 9)
        self.assertEqual(repo.tags["mark"].value, 9)

        with self.assertRaisesRegex(RuntimeError, "already refers"):
            run_program(
                """
                git branch taken
                git config alias.make -l name '!
                    git branch $name
                '
                git make taken
                """
            )

    def test_label_parameters_create_refs_in_outer_function_frame(self):
        repo, output = run_program(
            """
            git config alias.inner -l label '!
                git branch $label
                git checkout $label
                git commit -m 3
            '
            git config alias.outer '!
                git inner made
                git checkout made
                git show
            '
            git outer
            """
        )

        self.assertEqual(output, "3\n")
        self.assertNotIn("made", repo.branches)

    def test_protected_branch_parameters_can_target_main_and_current_but_not_be_deleted(self):
        repo, output = run_program(
            """
            git checkout -b work
            git commit -m 1
            git config alias.bump -p target '!
                git checkout $target
                git commit -m 2
            '
            git bump work
            git show work
            git bump main
            git show main
            """
        )

        self.assertEqual(output, "2\n2\n")
        self.assertEqual(repo.branches["work"].value, 2)
        self.assertEqual(repo.branches["main"].value, 2)
        self.assertEqual(repo.HEAD, "work")

        with self.assertRaisesRegex(ParseError, "branch deletion expects"):
            run_program(
                """
                git checkout -b work
                git config alias.bad -p target '!
                    git branch -d $target
                '
                git bad work
                """
            )

        with self.assertRaisesRegex(RuntimeError, "does not exist"):
            run_program(
                """
                git config alias.bump -p target '!
                    git checkout $target
                '
                git bump missing
                """
            )

    def test_tag_parameters_require_existing_tags(self):
        repo, output = run_program(
            """
            git commit -m 6
            git tag saved
            git commit -m 9
            git config alias.peek -t mark '!
                git show $mark
            '
            git peek saved
            """
        )

        self.assertEqual(output, "6\n")
        self.assertEqual(repo.tags["saved"].value, 6)

        with self.assertRaisesRegex(RuntimeError, "tag saved does not exist"):
            run_program(
                """
                git branch saved
                git config alias.peek -t mark '!
                    git show $mark
                '
                git peek saved
                """
            )

    def test_branch_listing_shows_function_bindings_and_protected_branches(self):
        repo, output = run_program(
            """
            git checkout -b feature
            git branch result
            git config alias.inspect -b output -p owner '!
                git branch scratch
                git checkout scratch
                git branch
            '
            git inspect result main
            """
        )

        self.assertEqual(
            output,
            "   main ! -> caller:feature\n"
            " * scratch\n"
            "   output -> caller:result\n"
            "   owner ! -> caller:main\n",
        )
        self.assertEqual(repo.HEAD, "feature")

    def test_branch_listing_shows_nested_binding_layers(self):
        repo, output = run_program(
            """
            git branch result
            git config alias.inner -b target '!
                git branch
            '
            git config alias.outer -b output '!
                git inner $output
            '
            git outer result
            """
        )

        self.assertEqual(
            output,
            " * main ! -> caller:main\n"
            "   target -> caller:output -> caller:result\n",
        )

    def test_global_exit_stops_execution(self):
        repo, output = run_program(
            """
            git commit -m 1 && exit && git commit -m 2
            git show
            """
        )

        self.assertEqual(output, "")
        self.assertEqual(repo.branches["main"].value, 1)


if __name__ == "__main__":
    unittest.main()
