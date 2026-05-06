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

    def test_pull_imports_requested_alias_definitions_without_running_program(self):
        library = os.path.join(os.getcwd(), f"tmp_library_{uuid.uuid4().hex}.gs")
        try:
            with open(library, "w", encoding="utf-8") as file:
                file.write(
                    "git commit 99\n"
                    "git config alias.bump 'commit 1'\n"
                    "git config alias.bump 'commit 2'\n"
                    "git config alias.say -s text '!git commit -m text'\n"
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

            with self.assertRaisesRegex(RuntimeError, "Alias not found"):
                run_statements(f'git pull "{library_arg}" missing\n')

            repo = run_statements(
                f'git pull "{library_arg}"\n'
                "git bump\n"
            )
            self.assertIn("say", repo.aliases)
            self.assertEqual(repo.branches["main"].value, 2)

            with self.assertRaisesRegex(RuntimeError, "global scope"):
                run_statements(
                    f'git config alias.bad "!git pull \\"{library_arg}\\" bump"\n'
                    "git bad\n"
                )
        finally:
            if os.path.exists(library):
                os.unlink(library)

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
