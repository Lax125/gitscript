from pathlib import Path

from gitscript.lexer import LexError, TokenKind, lex_statement, strip_comment


class PreprocessError(RuntimeError):
    pass


def preprocess_file(filename: str, stack: list[Path] | None = None) -> tuple[str, Path]:
    path = Path(filename).resolve()
    stack = [] if stack is None else list(stack)
    if path in stack:
        cycle = " -> ".join(str(item) for item in [*stack, path])
        raise PreprocessError(f"git clone cycle detected: {cycle}")

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PreprocessError(str(exc)) from exc

    return preprocess_source(source, path.parent, [*stack, path]), path.parent


def preprocess_source(source: str, base_dir: str | Path | None = None, stack: list[Path] | None = None) -> str:
    base = Path.cwd() if base_dir is None else Path(base_dir)
    stack = [] if stack is None else list(stack)
    lines = source.splitlines()
    output: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        clone_path = _clone_path(line, line_number)
        if clone_path is None:
            output.append(line)
            continue

        path = Path(clone_path)
        if not path.is_absolute():
            path = base / path
        cloned_source, _ = preprocess_file(str(path), stack)
        output.append("git init")
        output.extend(cloned_source.splitlines())

    return "\n".join(output)


def _clone_path(line: str, line_number: int) -> str | None:
    stripped = strip_comment(line).strip()
    if not stripped:
        return None
    if not stripped.startswith("git clone") and stripped != "git clone":
        return None

    try:
        tokens = lex_statement(stripped, line_number)
    except LexError:
        return None

    if len(tokens) < 2 or tokens[0].kind != TokenKind.GIT or tokens[1].kind != TokenKind.CLONE:
        return None
    if len(tokens) != 3:
        raise PreprocessError(f"Line {line_number}: git clone expects exactly one file path")
    return tokens[2].value
