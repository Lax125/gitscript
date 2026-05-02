import contextlib
import io
import unittest

from gitscript.parser import parse
from gitscript.repo import Repo


def run_program(source: str) -> tuple[Repo, str]:
    repo = Repo()
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        for statement in parse(source):
            statement.run(repo)

    return repo, output.getvalue()


class StatementExecutionTests(unittest.TestCase):
    def test_commit_branch_merge_and_show(self):
        repo, output = run_program(
            """
            git commit -m 7
            git branch seven
            git commit -m 5
            git merge seven -s=+
            git show
            """
        )

        self.assertEqual(output, "12\n")
        self.assertEqual(repo.branches["main"].value, 12)
        self.assertEqual(repo.branches["seven"].value, 7)

    def test_commit_string_and_log(self):
        repo, output = run_program(
            """
            git commit -m "Hello"
            git log
            """
        )

        self.assertEqual(output, "Hello\n")
        self.assertEqual(repo.branches["main"].value, ord("H"))

    def test_conflict_loop_runs_until_refs_are_equal(self):
        repo, output = run_program(
            """
            git checkout -b a
            git commit -m 48
            git checkout -b b
            git commit -m 18

            <<<<<<< a
                git checkout a
                git merge b -s=-
            =======
                git checkout b
                git merge a -s=-
            >>>>>>> b

            git show
            """
        )

        self.assertEqual(output, "6\n")
        self.assertEqual(repo.branches["a"].value, 6)
        self.assertEqual(repo.branches["b"].value, 6)

    def test_reset_tag_cherry_pick_and_rebase(self):
        repo, output = run_program(
            """
            git commit -m 1
            git tag one
            git commit -m 2
            git checkout -b feature
            git commit -m 3
            git reset one
            git cherry-pick feature
            git checkout main
            git commit -m 4
            git checkout feature
            git rebase main
            git show
            """
        )

        self.assertEqual(output, "1\n")
        self.assertEqual(repo.branches["main"].value, 4)
        self.assertEqual(repo.branches["feature"].value, 1)
        self.assertEqual(repo.branches["feature"].parent.value, 4)


if __name__ == "__main__":
    unittest.main()
