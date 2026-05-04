import argparse
import sys
from collections.abc import Sequence

from gitscript.parser import IncompleteInput, ParseError, parse, parse_repl
from gitscript.repo import Repo
from gitscript.statements import ExitSignal


def run_statements(source: str, repo: Repo | None = None) -> Repo:
    if repo is None:
        repo: Repo = Repo()

    try:
        for statement in parse(source):
            statement.run(repo)
    except ExitSignal:
        pass

    return repo


def run_file(filename: str) -> Repo:
    with open(filename, encoding="utf-8") as file:
        return run_statements(file.read())


def repl() -> None:
    repo = Repo()
    buffer: list[str] = []

    while True:
        try:
            line = input("... " if buffer else f"gitscript ({repo.HEAD}) > ")
        except EOFError:
            print(flush=True)
            return

        if not buffer and line.strip() in {"exit", "quit"}:
            return

        if not buffer and not line.strip():
            continue

        buffer.append(line)
        try:
            statements = parse_repl(buffer)
        except IncompleteInput:
            continue
        except ParseError as exc:
            print(exc, file=sys.stderr, flush=True)
            buffer.clear()
            continue

        try:
            for statement in statements:
                statement.run(repo)
        except ExitSignal:
            return
        except Exception as exc:
            print(exc, file=sys.stderr, flush=True)

        buffer.clear()


def main(argv: Sequence[str] | None = None) -> int:
    arg_parser = argparse.ArgumentParser(prog="gitscript", description="Run GitScript programs.")
    arg_parser.add_argument("filename", nargs="?", help="GitScript file to run. Starts a REPL when omitted.")
    args = arg_parser.parse_args(argv)

    if args.filename is None:
        repl()
        return 0

    try:
        run_file(args.filename)
    except (OSError, ParseError, RuntimeError, ValueError) as exc:
        print(exc, file=sys.stderr, flush=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
