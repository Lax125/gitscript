import contextlib
import io
from unittest.mock import patch

from gitscript.parser import parse
from gitscript.repo import Repo


def run_program(source: str, inputs: list[str] | None = None) -> tuple[Repo, str]:
    repo = Repo()
    output = io.StringIO()
    input_values = iter(inputs or [])

    with contextlib.redirect_stdout(output):
        with patch("builtins.input", side_effect=lambda: next(input_values)):
            for statement in parse(source):
                statement.run(repo)

    return repo, output.getvalue()
