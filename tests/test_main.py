import contextlib
import io
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

from gitscript.main import main, repl, run_file, run_statements
from gitscript.preprocessor import PreprocessError
from gitscript.repo import Repo


class MainTests(unittest.TestCase):
    def test_run_statements_executes_program_against_existing_repo(self):
        repo = Repo()

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            returned = run_statements(
                """
                git commit 5
                git show
                """,
                repo,
            )

        self.assertIs(returned, repo)
        self.assertEqual(repo.branches["main"].value, 5)
        self.assertEqual(output.getvalue(), "5\n")

    def test_run_file_executes_gitscript_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as file:
            file.write("git commit 13\n")
            filename = file.name

        try:
            repo = run_file(filename)
        finally:
            os.unlink(filename)

        self.assertEqual(repo.branches["main"].value, 13)

    def test_run_file_can_leave_worktree_at_script_directory_for_interactive_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = os.path.join(directory, "script.gs")
            with open(filename, "w", encoding="utf-8") as file:
                file.write("git commit 13\n")

            repo = run_file(filename, restore_worktree=False)

            self.assertEqual(repo.branches["main"].value, 13)
            self.assertEqual(str(repo.core_worktree), os.path.abspath(directory))

    def test_clone_preprocesses_file_with_init_and_cycle_detection(self):
        suffix = uuid.uuid4().hex
        initial = os.path.join(os.getcwd(), f"tmp_initial_{suffix}.gs")
        cloned = os.path.join(os.getcwd(), f"tmp_cloned_{suffix}.gs")
        try:
            with open(cloned, "w", encoding="utf-8") as file:
                file.write("git commit 8\n")
            with open(initial, "w", encoding="utf-8") as file:
                file.write(f"git commit 4\ngit clone {os.path.basename(cloned)}\ngit commit 9\n")

            repo = run_file(initial)

            self.assertEqual(repo.branches["main"].value, 9)
            self.assertEqual(repo.branches["main"].parent.value, 8)
            self.assertEqual(repo.branches["main"].parent.parent.value, 0)

            with open(cloned, "w", encoding="utf-8") as file:
                file.write(f"git clone {os.path.basename(initial)}\n")
            with self.assertRaises(PreprocessError):
                run_file(initial)
        finally:
            for filename in (initial, cloned):
                if os.path.exists(filename):
                    os.unlink(filename)

    def test_core_worktree_controls_clone_paths_and_survives_init(self):
        suffix = uuid.uuid4().hex
        directory = os.path.join(os.getcwd(), f"tmp_worktree_{suffix}")
        initial = os.path.join(os.getcwd(), f"tmp_initial_{suffix}.gs")
        cloned = os.path.join(directory, "cloned.gs")
        try:
            directory_arg = directory.replace("\\", "/")
            os.makedirs(directory)
            with open(cloned, "w", encoding="utf-8") as file:
                file.write("git commit 8\n")
            with open(initial, "w", encoding="utf-8") as file:
                file.write(
                    f'git config core.worktree "{directory_arg}"\n'
                    "git init\n"
                    "git clone cloned.gs\n"
                    "git commit 9\n"
                )

            repo = run_file(initial)

            self.assertEqual(repo.branches["main"].value, 9)
            self.assertEqual(repo.branches["main"].parent.value, 8)
            self.assertEqual(str(repo.core_worktree), os.getcwd())
        finally:
            for filename in (initial, cloned):
                if os.path.exists(filename):
                    os.unlink(filename)
            if os.path.isdir(directory):
                os.rmdir(directory)

    def test_pull_imports_requested_alias_definitions_without_running_program(self):
        library = os.path.join(os.getcwd(), f"tmp_library_{uuid.uuid4().hex}.gs")
        try:
            with open(library, "w", encoding="utf-8") as file:
                file.write(
                    "git commit 99\n"
                    "git config alias.bump 'commit 1'\n"
                    "git config alias.bump 'commit 2'\n"
                    "git config alias.say -s text '!git commit -m text'\n"
                    "git push bump say\n"
                )

            library_arg = library.replace("\\", "/")
            repo = run_statements(
                f'git pull "{library_arg}" imported:bump say\n'
                "git imported\n"
                'git say "A"\n'
            )

            self.assertIn("imported", repo.aliases)
            self.assertIn("say", repo.aliases)
            self.assertEqual(repo.branches["main"].value, ord("A"))
            self.assertEqual(repo.branches["main"].parent.value, 2)
            self.assertNotEqual(repo.branches["main"].parent.value, 99)

            with self.assertRaisesRegex(RuntimeError, "not pushed"):
                run_statements(f'git pull "{library_arg}" missing\n')

            with self.assertRaisesRegex(RuntimeError, "needs at least one alias"):
                run_statements(f'git pull "{library_arg}"\n')

            with self.assertRaisesRegex(RuntimeError, "global scope"):
                run_statements(
                    f'git config alias.bad "!git pull \\"{library_arg}\\" bump"\n'
                    "git bad\n"
                )
        finally:
            if os.path.exists(library):
                os.unlink(library)

    def test_pull_resolves_imported_dependencies_without_public_namespace_pollution(self):
        suffix = uuid.uuid4().hex
        helper = os.path.join(os.getcwd(), f"tmp_helper_{suffix}.gs")
        library = os.path.join(os.getcwd(), f"tmp_library_{suffix}.gs")
        try:
            helper_arg = helper.replace("\\", "/")
            library_arg = library.replace("\\", "/")
            with open(helper, "w", encoding="utf-8") as file:
                file.write(
                    "git config alias.inc 'commit 1'\n"
                    "git push inc\n"
                )
            with open(library, "w", encoding="utf-8") as file:
                file.write(
                    f'git pull "{helper_arg}" inc\n'
                    "git config alias.twice '!git inc && git inc'\n"
                    "git config alias.inc_amend 'inc --amend'\n"
                    "git push twice\n"
                    "git push inc_amend\n"
                )

            repo = run_statements(
                f'git pull "{library_arg}" twice inc_amend\n'
                "git twice\n"
                "git inc_amend\n"
                "git inc || git commit 9\n"
            )

            self.assertEqual(repo.branches["main"].value, 9)
            self.assertEqual(repo.branches["main"].parent.value, 1)
            self.assertNotIn("inc", repo.aliases)
        finally:
            for filename in (helper, library):
                if os.path.exists(filename):
                    os.unlink(filename)

    def test_pull_resolves_nested_imports_relative_to_loaded_file_worktree(self):
        suffix = uuid.uuid4().hex
        directory = os.path.join(os.getcwd(), f"tmp_modules_{suffix}")
        helper = os.path.join(directory, "helper.gs")
        library = os.path.join(directory, "library.gs")
        try:
            library_arg = library.replace("\\", "/")
            os.makedirs(directory)
            with open(helper, "w", encoding="utf-8") as file:
                file.write(
                    "git config alias.inc 'commit 1'\n"
                    "git push inc\n"
                )
            with open(library, "w", encoding="utf-8") as file:
                file.write(
                    'git pull "helper.gs" inc\n'
                    "git config alias.twice 'inc && git inc'\n"
                    "git push twice\n"
                )

            repo = run_statements(
                f'git pull "{library_arg}" twice\n'
                "git twice\n"
            )

            self.assertEqual(repo.branches["main"].value, 1)
            self.assertEqual(repo.branches["main"].parent.value, 1)
            self.assertEqual(str(repo.core_worktree), os.getcwd())
        finally:
            for filename in (helper, library):
                if os.path.exists(filename):
                    os.unlink(filename)
            if os.path.isdir(directory):
                os.rmdir(directory)

    def test_pull_resolves_intrafile_dependencies_and_requires_push(self):
        library = os.path.join(os.getcwd(), f"tmp_library_{uuid.uuid4().hex}.gs")
        try:
            library_arg = library.replace("\\", "/")
            with open(library, "w", encoding="utf-8") as file:
                file.write(
                    "git config alias.helper 'commit 3'\n"
                    "git config alias.public 'helper && git helper'\n"
                    "git push public\n"
                )

            repo = run_statements(
                f'git pull "{library_arg}" public\n'
                "git public\n"
                "git helper || git commit 5\n"
            )

            self.assertEqual(repo.branches["main"].value, 5)
            self.assertEqual(repo.branches["main"].parent.value, 3)

            with self.assertRaisesRegex(RuntimeError, "not pushed"):
                run_statements(f'git pull "{library_arg}" helper\n')
        finally:
            if os.path.exists(library):
                os.unlink(library)

    def test_pull_allows_transitive_pass_through_exports(self):
        suffix = uuid.uuid4().hex
        source = os.path.join(os.getcwd(), f"tmp_source_{suffix}.gs")
        passthrough = os.path.join(os.getcwd(), f"tmp_passthrough_{suffix}.gs")
        try:
            source_arg = source.replace("\\", "/")
            passthrough_arg = passthrough.replace("\\", "/")
            with open(source, "w", encoding="utf-8") as file:
                file.write(
                    "git config alias.my_alias 'commit 4'\n"
                    "git push my_alias\n"
                )
            with open(passthrough, "w", encoding="utf-8") as file:
                file.write(
                    f'git pull "{source_arg}" my_alias\n'
                    "git push my_alias\n"
                )

            repo = run_statements(
                f'git pull "{passthrough_arg}" my_alias\n'
                "git my_alias\n"
            )

            self.assertEqual(repo.branches["main"].value, 4)
        finally:
            for filename in (source, passthrough):
                if os.path.exists(filename):
                    os.unlink(filename)

    def test_pull_and_local_definitions_share_last_definition_per_file(self):
        suffix = uuid.uuid4().hex
        source = os.path.join(os.getcwd(), f"tmp_source_{suffix}.gs")
        local_wins = os.path.join(os.getcwd(), f"tmp_local_wins_{suffix}.gs")
        pull_wins = os.path.join(os.getcwd(), f"tmp_pull_wins_{suffix}.gs")
        try:
            source_arg = source.replace("\\", "/")
            local_wins_arg = local_wins.replace("\\", "/")
            pull_wins_arg = pull_wins.replace("\\", "/")
            with open(source, "w", encoding="utf-8") as file:
                file.write(
                    "git config alias.dep 'commit 8'\n"
                    "git push dep\n"
                )
            with open(local_wins, "w", encoding="utf-8") as file:
                file.write(
                    f'git pull "{source_arg}" dep\n'
                    "git config alias.dep 'commit 3'\n"
                    "git config alias.public 'dep'\n"
                    "git push public\n"
                )
            with open(pull_wins, "w", encoding="utf-8") as file:
                file.write(
                    "git config alias.dep 'commit 3'\n"
                    f'git pull "{source_arg}" dep\n'
                    "git config alias.public 'dep'\n"
                    "git push public\n"
                )

            local_repo = run_statements(
                f'git pull "{local_wins_arg}" public\n'
                "git public\n"
            )
            pull_repo = run_statements(
                f'git pull "{pull_wins_arg}" public\n'
                "git public\n"
            )

            self.assertEqual(local_repo.branches["main"].value, 3)
            self.assertEqual(pull_repo.branches["main"].value, 8)
        finally:
            for filename in (source, local_wins, pull_wins):
                if os.path.exists(filename):
                    os.unlink(filename)

    def test_pull_rejects_pushed_alias_that_is_not_defined_and_cycles(self):
        suffix = uuid.uuid4().hex
        bad = os.path.join(os.getcwd(), f"tmp_bad_{suffix}.gs")
        left = os.path.join(os.getcwd(), f"tmp_left_{suffix}.gs")
        right = os.path.join(os.getcwd(), f"tmp_right_{suffix}.gs")
        try:
            bad_arg = bad.replace("\\", "/")
            left_arg = left.replace("\\", "/")
            right_arg = right.replace("\\", "/")
            with open(bad, "w", encoding="utf-8") as file:
                file.write("git push missing\n")
            with self.assertRaisesRegex(RuntimeError, "not defined"):
                run_statements(f'git pull "{bad_arg}" missing\n')

            with open(left, "w", encoding="utf-8") as file:
                file.write(
                    f'git pull "{right_arg}" right\n'
                    "git config alias.left 'commit 1'\n"
                    "git push left\n"
                )
            with open(right, "w", encoding="utf-8") as file:
                file.write(
                    f'git pull "{left_arg}" left\n'
                    "git config alias.right 'commit 2'\n"
                    "git push right\n"
                )

            with self.assertRaisesRegex(RuntimeError, "cycle detected"):
                run_statements(f'git pull "{left_arg}" left\n')
        finally:
            for filename in (bad, left, right):
                if os.path.exists(filename):
                    os.unlink(filename)

    def test_main_runs_file_when_filename_is_given(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as file:
            file.write("git commit 21\ngit show\n")
            filename = file.name

        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                exit_code = main([filename])
        finally:
            os.unlink(filename)

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue(), "21\n")

    def test_main_starts_repl_when_filename_is_omitted(self):
        with patch("gitscript.main.repl") as repl_mock:
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        repl_mock.assert_called_once_with()

    def test_main_visualize_starts_graph_for_repl(self):
        with patch("gitscript.main.GraphVisualizer") as visualizer_class:
            visualizer = visualizer_class.return_value
            with patch("gitscript.main.repl") as repl_mock:
                exit_code = main(["-v"])

        self.assertEqual(exit_code, 0)
        visualizer_class.assert_called_once_with()
        visualizer.start.assert_called_once()
        repl_mock.assert_called_once()
        self.assertIs(repl_mock.call_args.args[0].visualizer, visualizer)

    def test_main_visualize_runs_file_with_live_graph(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as file:
            file.write("git commit 21\n")
            filename = file.name

        try:
            with patch("gitscript.main.GraphVisualizer") as visualizer_class:
                visualizer = visualizer_class.return_value
                exit_code = main(["-v", filename])
        finally:
            os.unlink(filename)

        self.assertEqual(exit_code, 0)
        visualizer.start.assert_called_once()
        self.assertGreaterEqual(visualizer.update.call_count, 2)

    def test_main_interactive_runs_file_then_starts_repl_with_script_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = os.path.join(directory, "script.gs")
            with open(filename, "w", encoding="utf-8") as file:
                file.write("git commit 21\n")

            with patch("gitscript.main.repl") as repl_mock:
                exit_code = main(["-i", filename])

            self.assertEqual(exit_code, 0)
            repl_mock.assert_called_once()
            repo = repl_mock.call_args.args[0]
            self.assertEqual(repo.branches["main"].value, 21)
            self.assertEqual(str(repo.core_worktree), os.path.abspath(directory))

    def test_main_interactive_repl_resolves_paths_from_script_directory(self):
        output = io.StringIO()
        inputs = iter(["git clone sibling.gs", "git show", "quit"])
        with tempfile.TemporaryDirectory() as directory:
            filename = os.path.join(directory, "script.gs")
            sibling = os.path.join(directory, "sibling.gs")
            with open(filename, "w", encoding="utf-8") as file:
                file.write("git commit 21\n")
            with open(sibling, "w", encoding="utf-8") as file:
                file.write("git commit 34\n")

            with patch("builtins.input", side_effect=lambda prompt="": next(inputs)):
                with contextlib.redirect_stdout(output):
                    exit_code = main(["-i", filename])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue(), "34\n")

    def test_repl_runs_statements_and_keeps_repo_state(self):
        output = io.StringIO()
        inputs = iter(["git commit 4", "git commit 6", "git show", "quit"])

        with patch("builtins.input", side_effect=lambda prompt="": next(inputs)):
            with contextlib.redirect_stdout(output):
                repl()

        self.assertEqual(output.getvalue(), "6\n")

    def test_repl_accumulates_conflict_block_before_running(self):
        output = io.StringIO()
        inputs = iter(
            [
                "git checkout -b a",
                "git commit 6",
                "git checkout -b b",
                "git commit 1",
                "git merge -s gt",
                "<<<<<<< a",
                "git checkout a",
                "git cherry-pick b -s=sub",
                "git merge --continue",
                "=======",
                "git merge --abort",
                ">>>>>>> main",
                "git show a",
                "quit",
            ]
        )

        with patch("builtins.input", side_effect=lambda prompt="": next(inputs)):
            with contextlib.redirect_stdout(output):
                repl()

        self.assertEqual(output.getvalue(), "0\n")


if __name__ == "__main__":
    unittest.main()
