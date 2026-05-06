import unittest
from textwrap import dedent

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
            git commit --amend 8
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
            'git commit -m\n'
            'git log root..HEAD\n'
            'git commit 0\n'
            'git log -n 1\n',
            inputs=["Yo"],
        )

        self.assertEqual(output, "Yo\n\x00\n")
        self.assertEqual(repo.branches["main"].value, 0)

    def test_string_commits_do_not_allow_amend(self):
        with self.assertRaises(ParseError):
            parse('git commit --amend -m "unsafe"')

        with self.assertRaises(ParseError):
            parse('git commit --amend -m\n')

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
            git commit 1
            git commit 2
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
            git tag old HEAD~1
            git show saved
            git show old
            """
        )

        self.assertEqual(output, "1\n2\n1\n")
        self.assertEqual(repo.branches["one"].value, 1)
        self.assertEqual(repo.branches["two"].value, 1)
        self.assertIn("temp", repo.branches)
        self.assertEqual(repo.tags["saved"].value, 2)
        self.assertEqual(repo.tags["old"].value, 1)

    def test_init_resets_global_repo_state_config_and_aliases(self):
        repo, output = run_program(
            """
            git config commit.verbose 1
            git config alias.c 'commit'
            git commit 5
            git branch old
            git tag saved
            git init
            git show
            git branch
            """
        )

        self.assertEqual(output, "0\n * main!\n")
        self.assertEqual(repo.branches["main"].value, 0)
        self.assertEqual(repo.tags, {})
        self.assertEqual(repo.aliases, {})
        self.assertFalse(repo.commit_verbose)

        with self.assertRaisesRegex(RuntimeError, "global scope"):
            run_program(
                """
                git config alias.do-init '!
                    git init
                '
                git do-init
                """
            )

    def test_branch_without_arguments_lists_global_branches(self):
        repo, output = run_program(
            """
            git checkout -b feature
            git branch
            """
        )

        self.assertEqual(output, "   main!\n * feature\n")
        self.assertEqual(repo.HEAD, "feature")

    def test_all_cherry_pick_strategies(self):
        repo, output = run_program(
            """
            git commit 10
            git branch ten
            git commit 3
            git cherry-pick ten -s=add
            git show
            git reset HEAD~1
            git cherry-pick ten -s=sub
            git show
            git reset HEAD~1
            git cherry-pick ten -s=mul
            git show
            git reset HEAD~1
            git cherry-pick ten -s=div
            git show
            git reset HEAD~1
            git cherry-pick ten -s=mod
            git show
            git reset HEAD~1
            git cherry-pick ten -s=gt
            git show
            git reset HEAD~1
            git cherry-pick ten -s=lt
            git show
            git reset HEAD~1
            git cherry-pick ten -s=gte
            git show
            git reset HEAD~1
            git cherry-pick ten -s=lte
            git show
            git reset HEAD~1
            git cherry-pick ten -s=eq
            git show
            git reset HEAD~1
            git cherry-pick ten -s=neq
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
            git commit 65
            git commit 66
            git branch data
            git commit 1
            git branch offset
            git show data~1
            git show data~(offset)
            git show data^
            """
        )

        self.assertEqual(output, "65\n65\n65\n")
        self.assertEqual(repo.branches["offset"].value, 1)

        with self.assertRaisesRegex(RuntimeError, "Ancestor does not exist"):
            run_program("git commit 1\ngit show HEAD~2\n")

    def test_commit_ranges_log_and_rev_list(self):
        repo, output = run_program(
            """
            git commit 65
            git commit 66
            git commit 0
            git log HEAD~3..HEAD
            git log --reverse -n 2 HEAD
            git rev-list -n=3 HEAD
            git rev-list --reverse HEAD~3..HEAD
            git rev-list HEAD..HEAD
            """
        )

        self.assertEqual(output, "\x00BA\nB\x00\n0\n66\n65\n65\n66\n0\n")
        self.assertEqual(repo.branches["main"].value, 0)

    def test_log_and_rev_list_default_to_head(self):
        repo, output = run_program(
            """
            git commit -m "Hi"
            git log --oneline
            git rev-list -n 2
            """
        )

        self.assertEqual(output, "Hi\x0072\n105\n")
        self.assertEqual(repo.branches["main"].value, ord("H"))

    def test_log_and_rev_list_all_include_all_visible_refs_and_override_exclusions(self):
        repo, output = run_program(
            """
            git tag root
            git commit 65
            git branch base
            git commit 66
            git branch right
            git checkout -b left base
            git commit 67

            git rev-list --reverse --all
            git rev-list --reverse --all base..right
            git log --reverse --all
            """
        )

        self.assertEqual(output, "0\n65\n66\n67\n0\n65\n66\n67\n\x00ABC\n")
        self.assertEqual(repo.branches["left"].value, 67)

    def test_multiple_commit_selectors_include_and_exclude_for_log_and_rev_list(self):
        repo, output = run_program(
            """
            git tag root
            git commit 65
            git branch base
            git commit 66
            git branch right
            git checkout -b left base
            git commit 67

            git rev-list --reverse root..left root..right
            git rev-list --reverse root..left left..right
            git log --reverse root..left root..right
            """
        )

        self.assertEqual(output, "65\n66\n67\n66\nABC\n")
        self.assertEqual(repo.branches["left"].value, 67)

    def test_symmetric_difference_ranges_for_log_and_rev_list(self):
        repo, output = run_program(
            """
            git commit 65
            git branch base
            git commit 66
            git branch right
            git checkout -b left base
            git commit 67

            git rev-list --reverse left...right
            git log --reverse left...right
            """
        )

        self.assertEqual(output, "66\n67\nBC\n")
        self.assertEqual(repo.branches["left"].value, 67)

    def test_multiple_commit_selectors_for_cherry_pick_and_revert(self):
        repo, output = run_program(
            """
            git tag root
            git commit 1
            git branch one
            git commit 2
            git branch two
            git reset root

            git cherry-pick one two -s=add
            git rev-list --reverse root..HEAD
            git reset root

            git cherry-pick root..two one..two
            git rev-list --reverse root..HEAD
            git revert root..HEAD HEAD^..HEAD
            git rev-list -n 1 HEAD
            """
        )

        self.assertEqual(output, "1\n3\n2\n-2\n")
        self.assertEqual(repo.branches["main"].value, -2)

    def test_git_log_graph_shows_values_chars_and_visible_refs(self):
        repo, output = run_program(
            """
            git tag root
            git commit 65
            git tag letter
            git commit 10
            git branch mark
            git log --graph
            """
        )

        self.assertEqual(
            output,
            dedent(r"""
                ╤ 2 value=10 char='\n' [HEAD -> main!, branch:mark]
                ╪ 1 value=65 char='A' [tag:letter]
                ╧ 0 value=0 char='\x00' [tag:root]
            """).lstrip(),
        )
        self.assertEqual(repo.branches["main"].value, 10)

    def test_git_log_graph_uses_separate_columns_for_branches(self):
        repo, output = run_program(
            """
            git commit 1
            git branch base
            git commit 2
            git branch right
            git checkout -b left base
            git commit 3
            git log --graph left right
            """
        )

        self.assertEqual(
            output,
            dedent(r"""
                ╤ 3 value=3 char='\x03' [HEAD -> left]
                ├─═ 2 value=2 char='\x02' [branch:main!, branch:right]
                ╪ 1 value=1 char='\x01' [branch:base]
                ╧ 0 value=0 char='\x00'
            """).lstrip()
        )
        self.assertEqual(repo.branches["left"].value, 3)

    def test_git_log_graph_can_use_same_column_for_unrelated_histories(self):
        repo, output = run_program(
            """
            git tag original
            git commit --amend 1
            git branch one
            git checkout -b two original
            git commit --amend 2
            git log --graph one two
            """
        )

        self.assertEqual(
            output,
            dedent(r"""
            ═ 2 value=2 char='\x02' [HEAD -> two]
            ═ 1 value=1 char='\x01' [branch:main!, branch:one]
            """).lstrip()
        )
        self.assertEqual(repo.branches["two"].value, 2)

    def test_git_log_graph_shows_commit_parameters_in_function_frames(self):
        repo, output = run_program(
            """
            git commit 65
            git branch source
            git commit 66
            git config alias.inspect -c selected '!
                git log --graph $selected HEAD
            '
            git inspect source
            """
        )

        self.assertEqual(
            output,
            dedent(r"""
                ╤ 2 value=66 char='B' [HEAD -> main!]
                ╪ 1 value=65 char='A' [param:selected]
                ╧ 0 value=0 char='\x00'
            """).lstrip()
        )
        self.assertEqual(repo.branches["main"].value, 66)

    def test_git_log_graph_keeps_converging_branches_readable(self):
        repo, output = run_program(
            """
            git tag root
            git commit 1
            git checkout -b a root
            git commit 2
            git commit 3
            git checkout main
            git commit 4
            git checkout -b b root
            git commit 5
            git log --graph a b main
            """
        )

        self.assertEqual(
            output,
            dedent(r"""
                ╤ 5 value=5 char='\x05' [HEAD -> b]
                │ ╤ 4 value=4 char='\x04' [branch:main!]
                │ │ ╤ 3 value=3 char='\x03' [branch:a]
                ├─┼─╧ 2 value=2 char='\x02'
                ├─╧ 1 value=1 char='\x01'
                ╧ 0 value=0 char='\x00' [tag:root]
            """).lstrip()
        )
        self.assertEqual(repo.branches["b"].value, 5)

    def test_git_log_graph_reuses_ended_columns_immediately(self):
        repo, output = run_program(
            """
            git tag root
            git commit 1
            git checkout -b a root
            git commit 2
            git checkout -b b root
            git commit 3
            git checkout -b c root
            git commit 4
            git log --graph main a b c
            """
        )

        self.assertEqual(
            output,
            dedent(r"""
                ╤ 4 value=4 char='\x04' [HEAD -> c]
                ├─═ 3 value=3 char='\x03' [branch:b]
                ├─═ 2 value=2 char='\x02' [branch:a]
                ├─═ 1 value=1 char='\x01' [branch:main!]
                ╧ 0 value=0 char='\x00' [tag:root]
            """).lstrip()
        )
        self.assertEqual(repo.branches["c"].value, 4)

    def test_git_log_graph_handles_limited_and_symdiff_selections(self):
        repo, output = run_program(
            """
            git commit 1
            git branch base
            git commit 2
            git branch right
            git checkout -b left base
            git commit 3
            git log --graph -n 2 left right
            git log --graph left...right
            """
        )

        self.assertEqual(
            output,
            dedent(r"""
                ═ 3 value=3 char='\x03' [HEAD -> left]
                ═ 2 value=2 char='\x02' [branch:main!, branch:right]
                ═ 3 value=3 char='\x03' [HEAD -> left]
                ═ 2 value=2 char='\x02' [branch:main!, branch:right]
            """).lstrip()
        )
        self.assertEqual(repo.branches["left"].value, 3)

    def test_git_log_graph_all_includes_visible_refs_and_commit_parameters(self):
        repo, output = run_program(
            """
            git commit 1
            git branch saved
            git reset HEAD~1
            git config alias.inspect -c source '!
                git commit 2
                git log --graph --all
            '
            git inspect saved
            """
        )

        self.assertEqual(
            output,
            dedent(r"""
                ╤ 2 value=2 char='\x02' [HEAD -> main!]
                ├─═ 1 value=1 char='\x01' [param:source]
                ╧ 0 value=0 char='\x00'
            """).lstrip(),
        )
        self.assertEqual(repo.branches["main"].value, 2)

    def test_git_log_graph_all_handles_leftwards_branching(self):
        repo, output = run_program(
            """
            git tag root
            git commit 1
            git checkout -b other root
            git commit 2
            git checkout main
            git commit 3
            git log --graph --all
            """
        )

        self.assertEqual(
            output,
            dedent(r"""
                ╤ 3 value=3 char='\x03' [HEAD -> main!]
                │ ╤ 2 value=2 char='\x02' [branch:other]
                ╧─┤ 1 value=1 char='\x01'
                  ╧ 0 value=0 char='\x00' [tag:root]
            """).lstrip(),
        )
        self.assertEqual(repo.branches["main"].value, 3)
        self.assertEqual(repo.branches["other"].value, 2)

    def test_cherry_pick_and_revert_ref_and_range(self):
        repo, output = run_program(
            """
            git commit 1
            git commit 2
            git branch two
            git commit 3
            git cherry-pick two
            git rev-list -n 1 HEAD
            git revert two
            git rev-list -n 1 HEAD
            git cherry-pick HEAD~5..HEAD~3
            git rev-list -n 2 HEAD
            git reset HEAD~2
            git cherry-pick HEAD~5..HEAD~3 -s add
            git rev-list -n 2 HEAD
            git reset HEAD~2
            git cherry-pick HEAD~5..HEAD~3 -s max
            git rev-list -n 2 HEAD
            git revert HEAD~7..HEAD~5
            git rev-list -n 2 HEAD
            """
        )

        self.assertEqual(output, "2\n-2\n2\n1\n1\n-1\n2\n1\n-1\n-2\n")
        self.assertEqual(repo.branches["main"].value, -1)

    def test_rebase_replays_current_branch_onto_target(self):
        repo, output = run_program(
            """
            git commit 1
            git checkout -b feature
            git commit 2
            git commit 3
            git checkout main
            git commit 9
            git checkout feature
            git rebase main
            git rev-list -n 5 HEAD
            """
        )

        self.assertEqual(output, "3\n2\n9\n1\n0\n")
        self.assertEqual(repo.branches["feature"].parent.parent, repo.branches["main"])

    def test_merge_conflict_if_else_continue_and_abort(self):
        repo, output = run_program(
            """
            git checkout -b counter
            git commit 3
            git checkout -b one
            git commit 1

            git checkout main

            git merge -s gt
            <<<<<<< counter
                git checkout counter
                git cherry-pick one -s=sub
                git merge --continue
            =======
                git merge --abort
            >>>>>>> main

            git show counter

            git checkout main
            git commit 9
            git branch same
            git merge -s is
            <<<<<<< main
                git commit 1
            =======
                git commit 2
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
            git commit 2
            git checkout -b one
            git commit 1
            git checkout main

            git merge -s gt loop
            <<<<<<< counter
                git merge -s is inner
                <<<<<<< main
                    git checkout counter
                    git cherry-pick one -s=sub
                    git merge --continue loop
                =======
                    git merge --abort
                >>>>>>> main
            =======
                git merge --abort
            >>>>>>> main

            git show counter

            git merge -s gt exit
            <<<<<<< counter
                git merge --abort
            =======
                git merge -s is inner
                <<<<<<< main
                    git merge --abort exit
                =======
                    git commit 9
                >>>>>>> main
                git commit 8
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
            git commit 1
            git commit --amend 2
            git commit -m "Hi"
            git branch base
            git cherry-pick base
            git cherry-pick root..base
            git revert base
            git revert root..base
            git checkout -b feature root
            git commit 7
            git rebase main
            git config commit.verbose false
            git commit 99
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
            git commit 1
            git checkout -b one
            git commit 1
            git checkout main

            git config merge.verbosity 2
            git merge -s gt loop
            <<<<<<< counter
                git checkout counter
                git cherry-pick one -s=sub
                git merge --continue loop
            =======
                git merge --abort loop
            >>>>>>> main

            git config merge.verbosity 0
            git checkout main
            git merge -s eq
            <<<<<<< main
                git commit 9
            =======
                git commit 8
            >>>>>>> counter

            git show counter
            """
        )

        self.assertEqual(output, "0\n")
        self.assertIn("[merge] begin label=loop condition=gt", debug)
        self.assertIn("[merge] check label=loop condition=gt left=1 right=0 selected=top", debug)
        self.assertIn("[merge] continue target=loop handled_by=loop", debug)
        self.assertIn("[merge] check label=loop condition=gt left=0 right=0 selected=bottom", debug)
        self.assertIn("[merge] abort target=loop handled_by=loop", debug)
        self.assertNotIn("condition=eq", debug)
        self.assertEqual(repo.branches["counter"].value, 0)

    def test_statement_separator_and_true_false_integer_literals(self):
        repo, output = run_program(
            """
            git commit true && git commit false && git rev-list -n 2 HEAD
            """
        )

        self.assertEqual(output, "0\n1\n")
        self.assertEqual(repo.branches["main"].value, 0)

    def test_statement_separator_treats_merge_conflict_as_one_statement(self):
        repo, output = run_program(
            """
            git checkout -b counter
            git commit 1
            git checkout main
            git merge -s gt
            <<<<<<< counter
                git merge --abort
            =======
                git commit 9
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
            """
            git merge
            <<<<<<< counter || git show
            =======
            >>>>>>> main
            """,
        ]
        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(ParseError):
                    parse(source)

    def test_statement_composition_can_include_merge_conflicts(self):
        repo, output = run_program(
            """
            git checkout -b counter
            git commit 1
            git checkout main
            git merge -s gt && git show counter
            <<<<<<< counter
                git merge --abort
            =======
                git commit 9
            >>>>>>> main
            """
        )

        self.assertEqual(output, "1\n")
        self.assertEqual(repo.branches["counter"].value, 1)

    def test_error_recovery_runs_fallback_for_runtime_errors(self):
        repo, output = run_program(
            """
            git commit 10
            git checkout -b zero
            git commit 0
            git checkout main
            git cherry-pick zero -s=div || git commit 99
            git show
            git show missing || git commit 7
            git show
            """
        )

        self.assertEqual(output, "99\n7\n")
        self.assertEqual(repo.branches["main"].value, 7)

    def test_error_recovery_handles_integer_input_errors(self):
        repo, output = run_program(
            """
            git commit || git commit 0
            git show
            """,
            ["not-an-int"],
        )

        self.assertEqual(output, "0\n")
        self.assertEqual(repo.branches["main"].value, 0)

    def test_sequence_skips_right_side_after_error(self):
        with self.assertRaisesRegex(RuntimeError, "missing"):
            run_program("git show missing && git commit 1")

    def test_anonymous_block_groups_multiple_statements(self):
        repo, output = run_program(
            """
            '!
                git commit 1
                git commit 2
            ' || git commit 3
            git show
            """
        )

        self.assertEqual(output, "2\n")
        self.assertEqual(repo.branches["main"].value, 2)

    def test_anonymous_blocks_can_nest_and_strings_can_contain_single_quotes(self):
        repo, output = run_program(
            """
            git tag root
            '!
                git commit -m "don't"
                '!git commit 2'
            '
            git show HEAD~5
            git show HEAD~1
            git show
            """
        )

        self.assertEqual(output, "116\n100\n2\n")
        self.assertEqual(repo.branches["main"].value, 2)

    def test_shortform_aliases_support_repeated_substitution(self):
        repo, output = run_program(
            """
            git config alias.c 'commit'
            git config alias.cm 'c'
            git cm 5
            git show
            """
        )

        self.assertEqual(output, "5\n")
        self.assertEqual(repo.branches["main"].value, 5)

    def test_shortform_expansion_accepts_one_composed_statement(self):
        repo, output = run_program("git config alias.twice 'commit 20 && git show'\n")

        self.assertEqual(output, "")
        self.assertIn("twice", repo.aliases)

        repo, output = run_program(
            """
            git config alias.twice 'commit 20 && git show'
            git twice
            """
        )

        self.assertEqual(output, "20\n")
        self.assertEqual(repo.branches["main"].value, 20)

    def test_shortform_expansion_can_commit_multiline_string(self):
        repo, output = run_program(
            '''\
git tag root
git config alias.say 'commit -m'
git say """A
B"""
git log root..HEAD
'''
        )

        self.assertEqual(output, "A\nB\n")
        self.assertEqual(repo.branches["main"].value, ord("A"))

    def test_shortform_expansion_cannot_define_alias(self):
        with self.assertRaisesRegex(RuntimeError, "cannot expand to an alias definition"):
            run_program(
                """
                git config alias.make-short "config alias.c 'commit'"
                git make-short
                """
            )

    def test_function_body_cannot_define_alias(self):
        with self.assertRaisesRegex(ParseError, "cannot define aliases"):
            run_program('git config alias.bad \'!git config alias.c "commit"\'\n')

        with self.assertRaisesRegex(ParseError, "cannot define aliases"):
            run_program(
                """
                git config alias.bad '!git commit 1 && git config alias.c "commit"'
                """
            )

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
            git commit 10
            git branch ten
            git checkout -b out root
            git config alias.use -i amount -s text -c source -c root_ref -m condition -o strategy '!
                git checkout main
                git cherry-pick $source -s=$strategy
                git merge -s $condition
                <<<<<<< main
                    git commit $amount
                    git commit -m "$text"
                =======
                    git commit 0
                >>>>>>> $root_ref
            '
            git use 7 "A" ten root gt max
            git rev-list --reverse root..out
            """
        )

        self.assertEqual(output, "10\n7\n65\n")
        self.assertEqual(repo.branches["out"].value, ord("A"))
        self.assertEqual(repo.call_stack, [])

        with self.assertRaises(ParseError):
            run_program(
                """
                git config alias.use -c source '!
                    git show $source
                '
                git use HEAD~1..HEAD
                """
            )

    def test_function_defaults_named_arguments_and_exit(self):
        repo, output = run_program(
            """
            git config alias.make -i amount=1 '!
                git commit $amount
                exit
                git commit 99
            '
            git make
            git make --amount 4
            git rev-list -n 3 HEAD
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
                git commit 5
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
            git commit 1
            git config alias.bump '!
                git checkout main
                git commit 2
                git branch temp
                exit
                git commit 99
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
            git commit 4
            git tag saved
            git commit 9
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
            git commit 7
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
            git commit 4
            git config alias.make_refs -l branch_name -l tag_name '!
                git branch $branch_name
                git checkout $branch_name
                git commit 9
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
                git commit 3
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
            git commit 1
            git config alias.bump -p target '!
                git checkout $target
                git commit 2
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
            git commit 6
            git tag saved
            git commit 9
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
            "   main! -> caller:feature\n"
            " * scratch\n"
            "   output -> caller:result\n"
            "   owner! -> caller:main\n",
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
            " * main! -> caller:main\n"
            "   target -> caller:output -> caller:result\n",
        )

    def test_global_exit_stops_execution(self):
        repo, output = run_program(
            """
            git commit 1 && exit && git commit 2
            git show
            """
        )

        self.assertEqual(output, "")
        self.assertEqual(repo.branches["main"].value, 1)


if __name__ == "__main__":
    unittest.main()
