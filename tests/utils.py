import contextlib
import io
from unittest.mock import patch

from gitscript.ansi import strip as strip_ansi
from gitscript.parser import parse
from gitscript.repo import Repo
from gitscript.statements import ExitSignal


def run_program(source: str, inputs: list[str] | None = None) -> tuple[Repo, str]:
    repo, output, _ = run_program_with_debug(source, inputs)
    return repo, output


def run_program_with_debug(source: str, inputs: list[str] | None = None) -> tuple[Repo, str, str]:
    repo = Repo()
    output = io.StringIO()
    debug = io.StringIO()
    input_values = iter(inputs or [])

    with contextlib.redirect_stdout(output):
        with contextlib.redirect_stderr(debug):
            with patch("builtins.input", side_effect=lambda: next(input_values)):
                try:
                    for statement in parse(source):
                        statement.run(repo)
                except ExitSignal:
                    pass

    return repo, strip_ansi(output.getvalue()), strip_ansi(debug.getvalue())
