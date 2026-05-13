import argparse
import sys
from collections.abc import Sequence

from gitscript import ansi
from gitscript.parser import IncompleteInput, ParseError, parse, parse_repl
from gitscript.preprocessor import PreprocessError, preprocess_file, preprocess_source
from gitscript.repo import Repo
from gitscript.statements import ExitSignal


def run_statements(
        source: str,
        repo: Repo | None = None,
        base_dir: str | None = None,
        preprocess: bool = True,
) -> Repo:
    if repo is None:
        repo: Repo = Repo()

    if preprocess:
        source = preprocess_source(source, repo.core_worktree if base_dir is None else base_dir)

    try:
        for statement in parse(source):
            statement.run(repo)
    except ExitSignal:
        pass

    return repo


def run_file(filename: str, repo: Repo | None = None, restore_worktree: bool = True) -> Repo:
    source, base_dir = preprocess_file(filename, restore_worktree=restore_worktree)
    return run_statements(source, repo=repo, base_dir=str(base_dir), preprocess=False)


def repl(repo: Repo | None = None) -> None:
    if repo is None:
        repo = Repo()
    buffer: list[str] = []

    while True:
        try:
            line = input(_prompt(repo, bool(buffer)))
        except EOFError:
            print(flush=True)
            return

        if not buffer and line.strip() in {"exit", "quit"}:
            return

        if not buffer and not line.strip():
            continue

        buffer.append(line)
        try:
            statements = parse_repl(preprocess_source("\n".join(buffer), repo.core_worktree).splitlines())
        except IncompleteInput:
            continue
        except (ParseError, PreprocessError) as exc:
            print(_format_error(exc), file=sys.stderr, flush=True)
            buffer.clear()
            continue

        try:
            for statement in statements:
                statement.run(repo)
        except ExitSignal:
            return
        except Exception as exc:
            print(_format_error(exc), file=sys.stderr, flush=True)

        buffer.clear()


def main(argv: Sequence[str] | None = None) -> int:
    arg_parser = argparse.ArgumentParser(prog="gitscript", description="Run GitScript programs.")
    arg_parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enter REPL mode after running the script.",
    )
    arg_parser.add_argument("filename", nargs="?", help="GitScript file to run. Starts a REPL when omitted.")
    args = arg_parser.parse_args(argv)

    if args.filename is None:
        repl()
        return 0

    try:
        repo = run_file(args.filename, restore_worktree=not args.interactive)
    except (OSError, ParseError, PreprocessError, RuntimeError, ValueError) as exc:
        print(_format_error(exc), file=sys.stderr, flush=True)
        return 1

    if args.interactive:
        repl(repo)

    return 0


def _prompt(repo: Repo, continuation: bool) -> str:
    if continuation:
        return ansi.paint("... ", ansi.DEBUG)
    return (
        ansi.paint("gitscript", ansi.DEBUG)
        + ansi.paint(" (", ansi.DEBUG)
        + ansi.paint(repo.HEAD, ansi.BRANCH)
        + ansi.paint(") > ", ansi.DEBUG)
    )


def _format_error(exc: Exception) -> str:
    return ansi.paint(exc, ansi.DEBUG)


if __name__ == "__main__":
    raise SystemExit(main())
