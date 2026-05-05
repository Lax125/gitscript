import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from gitscript.main import main, repl, run_file, run_statements
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
