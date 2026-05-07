from dataclasses import dataclass
from pathlib import Path

from gitscript.preprocessor import preprocess_file
from gitscript.statements import (
    AliasDefinition,
    DefineAlias,
    DefineFunction,
    FunctionDefinition,
    Pull,
    Push,
    Rescue,
    Sequence,
    Statement,
    StatementBlock,
)


_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_/")


@dataclass
class LoadedModule:
    path: Path
    definitions: dict[str, AliasDefinition | FunctionDefinition]
    exports: dict[str, str]


def import_aliases(repo, file_path: str, aliases: list[tuple[str, str]]) -> None:
    module = load_module(repo, Path(file_path), Path.cwd(), [])
    missing = [source_name for _, source_name in aliases if source_name not in module.exports]
    if missing:
        raise RuntimeError(f"Alias not pushed by {file_path}: {', '.join(missing)}")

    repo.aliases.update(module.definitions)
    for target_name, source_name in aliases:
        repo.aliases[target_name] = module.definitions[module.exports[source_name]]


def load_module(repo, file_path: Path, base_dir: Path, stack: list[Path]) -> LoadedModule:
    path = file_path if file_path.is_absolute() else base_dir / file_path
    path = path.resolve()

    cache = repo.import_cache
    if path in cache:
        return cache[path]
    if path in stack:
        cycle = " -> ".join(str(item) for item in [*stack, path])
        raise RuntimeError(f"git pull cycle detected: {cycle}")

    from gitscript.parser import parse, validate_function_body

    source, module_base = preprocess_file(str(path))
    statements = parse(source)
    local_definitions = _collect_alias_definitions(statements)
    pushed = _collect_pushes(statements)
    pulls = _collect_pulls(statements)

    for name in pushed:
        if name not in local_definitions:
            raise RuntimeError(f"Alias {name} is pushed by {path} but is not implemented")

    imported_names: dict[str, str] = {}
    all_definitions: dict[str, AliasDefinition | FunctionDefinition] = {}
    for pull in pulls:
        if not pull.aliases:
            raise RuntimeError("git pull needs at least one alias name")
        pulled_module = load_module(repo, Path(pull.file_path), module_base, [*stack, path])
        missing = [source_name for _, source_name in pull.aliases if source_name not in pulled_module.exports]
        if missing:
            raise RuntimeError(f"Alias not pushed by {pull.file_path}: {', '.join(missing)}")
        all_definitions.update(pulled_module.definitions)
        for target_name, source_name in pull.aliases:
            imported_names[target_name] = pulled_module.exports[source_name]

    local_names = {
        name: _qualified_name(path, name)
        for name in local_definitions
    }
    replacement_names = {**imported_names, **local_names}

    for name, definition in local_definitions.items():
        qualified_name = local_names[name]
        if isinstance(definition, DefineAlias):
            fragment = _rewrite_alias_fragment(definition.fragment, replacement_names)
            all_definitions[qualified_name] = AliasDefinition(fragment)
        else:
            body = _rewrite_source_aliases(definition.body, replacement_names)
            validate_function_body(body, definition.parameters)
            all_definitions[qualified_name] = FunctionDefinition(definition.parameters, body)

    module = LoadedModule(
        path=path,
        definitions=all_definitions,
        exports={name: local_names[name] for name in pushed},
    )
    cache[path] = module
    return module


def _qualified_name(path: Path, name: str) -> str:
    return f"_import/{abs(hash(path))}/{name}"


def _collect_alias_definitions(statements: list[Statement]) -> dict[str, DefineAlias | DefineFunction]:
    definitions: dict[str, DefineAlias | DefineFunction] = {}
    for statement in statements:
        _collect_alias_definition(statement, definitions)
    return definitions


def _collect_alias_definition(statement: Statement, definitions: dict[str, DefineAlias | DefineFunction]) -> None:
    if isinstance(statement, (DefineAlias, DefineFunction)):
        definitions[statement.name] = statement
        return
    if isinstance(statement, (Sequence, Rescue)):
        _collect_alias_definition(statement.left, definitions)
        _collect_alias_definition(statement.right, definitions)
        return
    if isinstance(statement, StatementBlock):
        for nested in statement.statements:
            _collect_alias_definition(nested, definitions)


def _collect_pushes(statements: list[Statement]) -> set[str]:
    pushes: set[str] = set()
    for statement in statements:
        _collect_push(statement, pushes)
    return pushes


def _collect_push(statement: Statement, pushes: set[str]) -> None:
    if isinstance(statement, Push):
        pushes.update(statement.aliases)
        return
    if isinstance(statement, (Sequence, Rescue)):
        _collect_push(statement.left, pushes)
        _collect_push(statement.right, pushes)
        return
    if isinstance(statement, StatementBlock):
        for nested in statement.statements:
            _collect_push(nested, pushes)


def _collect_pulls(statements: list[Statement]) -> list[Pull]:
    pulls: list[Pull] = []
    for statement in statements:
        _collect_pull(statement, pulls)
    return pulls


def _collect_pull(statement: Statement, pulls: list[Pull]) -> None:
    if isinstance(statement, Pull):
        pulls.append(statement)
        return
    if isinstance(statement, (Sequence, Rescue)):
        _collect_pull(statement.left, pulls)
        _collect_pull(statement.right, pulls)
        return
    if isinstance(statement, StatementBlock):
        for nested in statement.statements:
            _collect_pull(nested, pulls)


def _rewrite_alias_fragment(fragment: str, replacements: dict[str, str]) -> str:
    source = _rewrite_source_aliases("git " + fragment, replacements)
    return source[4:] if source.startswith("git ") else source


def _rewrite_source_aliases(source: str, replacements: dict[str, str]) -> str:
    result: list[str] = []
    i = 0
    expecting_command = False

    while i < len(source):
        if source.startswith('"""', i):
            end = source.find('"""', i + 3)
            if end == -1:
                result.append(source[i:])
                break
            result.append(source[i:end + 3])
            i = end + 3
            expecting_command = False
            continue
        if source[i] == "#":
            end = i
            while end < len(source) and source[end] not in "\r\n":
                end += 1
            result.append(source[i:end])
            i = end
            continue
        if source[i] in {"'", '"'}:
            end = _quoted_end(source, i)
            result.append(source[i:end])
            i = end
            expecting_command = False
            continue
        if source[i] in _NAME_CHARS:
            end = i + 1
            while end < len(source) and source[end] in _NAME_CHARS:
                end += 1
            word = source[i:end]
            if expecting_command:
                result.append(replacements.get(word, word))
                expecting_command = False
            else:
                result.append(word)
                expecting_command = word == "git"
            i = end
            continue
        result.append(source[i])
        if not source[i].isspace():
            expecting_command = False
        i += 1

    return "".join(result)


def _quoted_end(source: str, start: int) -> int:
    quote = source[start]
    i = start + 1
    escaped = False
    while i < len(source):
        char = source[i]
        if quote == '"' and escaped:
            escaped = False
        elif quote == '"' and char == "\\":
            escaped = True
        elif char == quote:
            return i + 1
        i += 1
    return len(source)
