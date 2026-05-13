from dataclasses import dataclass, field
from pathlib import Path

from gitscript.commit import Commit


@dataclass
class FunctionFrame:
    branches: dict[str, Commit] = field(default_factory=dict)
    tags: dict[str, Commit] = field(default_factory=dict)
    bindings: dict[str, "RefBinding"] = field(default_factory=dict)
    parameters: dict[str, str] = field(default_factory=dict)
    caller_head: str = "main"
    commit_verbose: bool = False
    merge_verbosity: int = 0


@dataclass
class BranchListingEntry:
    name: str
    current: bool
    protected: bool = False
    binding_chain: list[str] = field(default_factory=list)


@dataclass
class TagListingEntry:
    name: str
    commit: Commit
    bound: bool = False
    binding_chain: list[str] = field(default_factory=list)


class RefBinding:
    def resolve(self) -> Commit:
        raise NotImplementedError

    def is_branch(self) -> bool:
        return False

    def is_tag(self) -> bool:
        return False

    def is_protected(self) -> bool:
        return False

    def branch_binding_chain(self) -> list[str]:
        return []

    def tag_binding_chain(self) -> list[str]:
        return []

    def set_branch(self, commit: Commit) -> None:
        raise RuntimeError("Reference is not a branch")

    def create_branch(self, commit: Commit) -> None:
        raise RuntimeError("Reference cannot create a branch")

    def create_tag(self, commit: Commit) -> None:
        raise RuntimeError("Reference cannot create a tag")

    def delete_branch(self) -> None:
        raise RuntimeError("Reference is not a branch")

    def delete_tag(self) -> None:
        raise RuntimeError("Reference is not a tag")


@dataclass
class BranchBinding(RefBinding):
    branches: dict[str, Commit]
    name: str

    def resolve(self) -> Commit:
        if self.name not in self.branches:
            raise RuntimeError(f"Branch {self.name} does not exist")
        return self.branches[self.name]

    def is_branch(self) -> bool:
        return self.name in self.branches

    def branch_binding_chain(self) -> list[str]:
        if not self.is_branch():
            return []
        return [self.name]

    def set_branch(self, commit: Commit) -> None:
        if self.name not in self.branches:
            raise RuntimeError(f"Branch {self.name} does not exist")
        self.branches[self.name] = commit

    def delete_branch(self) -> None:
        if self.name not in self.branches:
            raise RuntimeError(f"Branch {self.name} does not exist")
        del self.branches[self.name]


@dataclass
class TagBinding(RefBinding):
    tags: dict[str, Commit]
    name: str

    def resolve(self) -> Commit:
        if self.name not in self.tags:
            raise RuntimeError(f"tag {self.name} does not exist")
        return self.tags[self.name]

    def is_tag(self) -> bool:
        return self.name in self.tags

    def tag_binding_chain(self) -> list[str]:
        if not self.is_tag():
            return []
        return [self.name]

    def delete_tag(self) -> None:
        if self.name not in self.tags:
            raise RuntimeError(f"tag {self.name} does not exist")
        del self.tags[self.name]


@dataclass
class NameBinding(RefBinding):
    branches: dict[str, Commit]
    tags: dict[str, Commit]
    name: str

    def resolve(self) -> Commit:
        if self.name in self.tags:
            return self.tags[self.name]
        if self.name in self.branches:
            return self.branches[self.name]
        raise RuntimeError(f"Unknown tag or branch: {self.name}")

    def is_branch(self) -> bool:
        return self.name in self.branches

    def is_tag(self) -> bool:
        return self.name in self.tags

    def branch_binding_chain(self) -> list[str]:
        if not self.is_branch():
            return []
        return [self.name]

    def tag_binding_chain(self) -> list[str]:
        if not self.is_tag():
            return []
        return [self.name]

    def set_branch(self, commit: Commit) -> None:
        if self.name not in self.branches:
            raise RuntimeError(f"Branch {self.name} does not exist")
        self.branches[self.name] = commit

    def create_branch(self, commit: Commit) -> None:
        if self.name in self.branches or self.name in self.tags:
            raise RuntimeError(f"Branch or tag {self.name} already exists")
        self.branches[self.name] = commit

    def create_tag(self, commit: Commit) -> None:
        if self.name in self.branches or self.name in self.tags:
            raise RuntimeError(f"Branch or tag {self.name} already exists")
        self.tags[self.name] = commit

    def delete_branch(self) -> None:
        if self.name not in self.branches:
            raise RuntimeError(f"Branch {self.name} does not exist")
        del self.branches[self.name]

    def delete_tag(self) -> None:
        if self.name not in self.tags:
            raise RuntimeError(f"tag {self.name} does not exist")
        del self.tags[self.name]


@dataclass
class CommitBinding(RefBinding):
    commit: Commit

    def resolve(self) -> Commit:
        return self.commit


@dataclass
class CallerBinding(RefBinding):
    binding: RefBinding
    caller_name: str

    def resolve(self) -> Commit:
        return self.binding.resolve()

    def is_branch(self) -> bool:
        return self.binding.is_branch()

    def is_tag(self) -> bool:
        return self.binding.is_tag()

    def is_protected(self) -> bool:
        return self.binding.is_protected()

    def branch_binding_chain(self) -> list[str]:
        if not self.is_branch():
            return []
        chain = self.binding.branch_binding_chain()
        if chain and chain[0] == self.caller_name:
            return chain
        return [self.caller_name, *chain]

    def tag_binding_chain(self) -> list[str]:
        if not self.is_tag():
            return []
        chain = self.binding.tag_binding_chain()
        if chain and chain[0] == self.caller_name:
            return chain
        return [self.caller_name, *chain]

    def set_branch(self, commit: Commit) -> None:
        self.binding.set_branch(commit)

    def create_branch(self, commit: Commit) -> None:
        self.binding.create_branch(commit)

    def create_tag(self, commit: Commit) -> None:
        self.binding.create_tag(commit)

    def delete_branch(self) -> None:
        self.binding.delete_branch()

    def delete_tag(self) -> None:
        self.binding.delete_tag()


@dataclass
class ProtectedBinding(RefBinding):
    binding: RefBinding
    name: str

    def resolve(self) -> Commit:
        return self.binding.resolve()

    def is_branch(self) -> bool:
        return self.binding.is_branch()

    def is_tag(self) -> bool:
        return self.binding.is_tag()

    def is_protected(self) -> bool:
        return True

    def branch_binding_chain(self) -> list[str]:
        return self.binding.branch_binding_chain()

    def tag_binding_chain(self) -> list[str]:
        return self.binding.tag_binding_chain()

    def set_branch(self, commit: Commit) -> None:
        self.binding.set_branch(commit)

    def create_branch(self, commit: Commit) -> None:
        self.binding.create_branch(commit)

    def create_tag(self, commit: Commit) -> None:
        self.binding.create_tag(commit)

    def delete_branch(self) -> None:
        if not self.binding.is_branch():
            self.binding.delete_branch()
        raise RuntimeError(f"Cannot delete protected branch {self.name}")

    def delete_tag(self) -> None:
        if not self.binding.is_tag():
            self.binding.delete_tag()
        raise RuntimeError(f"Cannot delete protected tag {self.name}")


def protect_binding(binding: RefBinding, name: str) -> RefBinding:
    return ProtectedBinding(binding, name)


class Repo:
    def __init__(self):
        visualizer = getattr(self, "visualizer", None)
        self.visualizer = visualizer
        self._visualizer_ready = False
        self.commits: list[Commit] = []
        self.next_commit_order = 0
        root = self.allocate_commit(0, None)

        self.branches = {"main": root}
        self.tags = {}
        self.HEAD = "main"
        self._commit_verbose = False
        self._merge_verbosity = 0
        self.core_worktree = Path.cwd()
        self.aliases = {}
        self.import_cache = {}
        self.call_stack: list[FunctionFrame] = []
        self._visualizer_ready = True
        self.notify_visualizer()

    def allocate_commit(self, value: int, parent: Commit | None) -> Commit:
        commit = Commit(value, parent, self.next_commit_order)
        self.next_commit_order += 1
        self.commits.append(commit)
        self.notify_visualizer()
        return commit

    def notify_visualizer(self) -> None:
        if self.visualizer is None or not self._visualizer_ready:
            return
        self.visualizer.update(self)

    def current_frame(self) -> FunctionFrame | None:
        if not self.call_stack:
            return None
        return self.call_stack[-1]

    @property
    def commit_verbose(self) -> bool:
        frame = self.current_frame()
        if frame is not None:
            return frame.commit_verbose
        return self._commit_verbose

    @commit_verbose.setter
    def commit_verbose(self, value: bool) -> None:
        frame = self.current_frame()
        if frame is not None:
            frame.commit_verbose = value
        else:
            self._commit_verbose = value

    @property
    def merge_verbosity(self) -> int:
        frame = self.current_frame()
        if frame is not None:
            return frame.merge_verbosity
        return self._merge_verbosity

    @merge_verbosity.setter
    def merge_verbosity(self, value: int) -> None:
        frame = self.current_frame()
        if frame is not None:
            frame.merge_verbosity = value
        else:
            self._merge_verbosity = value

    def push_function_frame(self, bindings: dict[str, RefBinding], parameters: dict[str, str]) -> None:
        caller_head = self.HEAD
        bindings = dict(bindings)
        bindings["main"] = protect_binding(
            self.bind_caller_branch(caller_head),
            "main",
        )
        self.call_stack.append(FunctionFrame(
            bindings=bindings,
            parameters=parameters,
            caller_head=caller_head,
            commit_verbose=self.commit_verbose,
            merge_verbosity=self.merge_verbosity,
        ))
        self.HEAD = "main"
        self.notify_visualizer()

    def pop_function_frame(self) -> None:
        frame = self.call_stack.pop()
        self.HEAD = frame.caller_head
        self.notify_visualizer()

    def resolve(self, tag_or_branch_name: str) -> Commit:
        binding = self._binding(tag_or_branch_name)
        if binding is not None:
            return binding.resolve()

        frame = self.current_frame()
        if frame is not None:
            if tag_or_branch_name in frame.tags:
                return frame.tags[tag_or_branch_name]
            if tag_or_branch_name in frame.branches:
                return frame.branches[tag_or_branch_name]
            raise RuntimeError(f"Unknown tag or branch: {tag_or_branch_name}")

        if tag_or_branch_name in self.tags:
            return self.tags[tag_or_branch_name]
        if tag_or_branch_name in self.branches:
            return self.branches[tag_or_branch_name]
        raise RuntimeError(f"Unknown tag or branch: {tag_or_branch_name}")

    def has(self, tag_or_branch_name: str) -> bool:
        return self.has_branch(tag_or_branch_name) or self.has_tag(tag_or_branch_name)

    def has_branch(self, name: str) -> bool:
        binding = self._binding(name)
        if binding is not None:
            return binding.is_branch()

        frame = self.current_frame()
        if frame is not None:
            return name in frame.branches
        return name in self.branches

    def has_tag(self, name: str) -> bool:
        binding = self._binding(name)
        if binding is not None:
            return binding.is_tag()

        frame = self.current_frame()
        if frame is not None:
            return name in frame.tags
        return name in self.tags

    def current_commit(self) -> Commit:
        return self.bind_branch(self.HEAD).resolve()

    def set_current_commit(self, commit: Commit) -> None:
        self.bind_branch(self.HEAD).set_branch(commit)
        self.notify_visualizer()

    def create_branch(self, name: str, commit: Commit) -> None:
        if name == "main" and self.current_frame() is not None:
            raise RuntimeError("Cannot create protected branch main")
        binding = self._binding(name)
        if binding is not None:
            if binding.is_branch() or binding.is_tag():
                raise RuntimeError(f"Branch or tag {name} already exists")
            binding.create_branch(commit)
            self.notify_visualizer()
            return
        if self.has(name):
            raise RuntimeError(f"Branch or tag {name} already exists")

        frame = self.current_frame()
        if frame is not None:
            frame.branches[name] = commit
        else:
            self.branches[name] = commit
        self.notify_visualizer()

    def delete_branch(self, name: str) -> None:
        if name == "main":
            raise RuntimeError("Cannot delete protected branch main")
        if self.HEAD == name:
            raise RuntimeError(f"Cannot delete current branch {name}")

        binding = self._binding(name)
        if binding is not None:
            binding.delete_branch()
            self.notify_visualizer()
            return

        frame = self.current_frame()
        if frame is not None:
            if name not in frame.branches:
                raise RuntimeError(f"Branch {name} does not exist")
            del frame.branches[name]
            self.notify_visualizer()
            return

        if name not in self.branches:
            raise RuntimeError(f"Branch {name} does not exist")
        del self.branches[name]
        self.notify_visualizer()

    def checkout(self, name: str) -> None:
        if not self.has_branch(name):
            raise RuntimeError(f"Branch {name} does not exist")
        self.HEAD = name
        self.notify_visualizer()

    def create_tag(self, name: str, commit: Commit) -> None:
        if name == "main" and self.current_frame() is not None:
            raise RuntimeError("Cannot create tag main")
        binding = self._binding(name)
        if binding is not None:
            if binding.is_branch() or binding.is_tag():
                raise RuntimeError(f"Branch or tag {name} already exists")
            binding.create_tag(commit)
            self.notify_visualizer()
            return
        if self.has(name):
            raise RuntimeError(f"Branch or tag {name} already exists")

        frame = self.current_frame()
        if frame is not None:
            frame.tags[name] = commit
        else:
            self.tags[name] = commit
        self.notify_visualizer()

    def delete_tag(self, name: str) -> None:
        binding = self._binding(name)
        if binding is not None:
            binding.delete_tag()
            self.notify_visualizer()
            return

        frame = self.current_frame()
        if frame is not None:
            if name not in frame.tags:
                raise RuntimeError(f"tag {name} does not exist")
            del frame.tags[name]
            self.notify_visualizer()
            return

        if name not in self.tags:
            raise RuntimeError(f"tag {name} does not exist")
        del self.tags[name]
        self.notify_visualizer()

    def bind_branch(self, name: str) -> RefBinding:
        binding = self._binding(name)
        if binding is not None:
            if not binding.is_branch():
                raise RuntimeError(f"Branch {name} does not exist")
            return binding

        frame = self.current_frame()
        if frame is not None:
            if name not in frame.branches:
                raise RuntimeError(f"Branch {name} does not exist")
            return BranchBinding(frame.branches, name)

        if name not in self.branches:
            raise RuntimeError(f"Branch {name} does not exist")
        return BranchBinding(self.branches, name)

    def bind_tag(self, name: str) -> RefBinding:
        binding = self._binding(name)
        if binding is not None:
            if not binding.is_tag():
                raise RuntimeError(f"tag {name} does not exist")
            return binding

        frame = self.current_frame()
        if frame is not None:
            if name not in frame.tags:
                raise RuntimeError(f"tag {name} does not exist")
            return TagBinding(frame.tags, name)

        if name not in self.tags:
            raise RuntimeError(f"tag {name} does not exist")
        return TagBinding(self.tags, name)

    def bind_name(self, name: str) -> RefBinding:
        binding = self._binding(name)
        if binding is not None:
            return binding

        frame = self.current_frame()
        if frame is not None:
            return NameBinding(frame.branches, frame.tags, name)
        return NameBinding(self.branches, self.tags, name)

    def bind_caller_branch(self, name: str) -> RefBinding:
        return CallerBinding(self.bind_branch(name), self.visible_name(name))

    def bind_caller_name(self, name: str) -> RefBinding:
        return CallerBinding(self.bind_name(name), self.visible_name(name))

    def bind_caller_tag(self, name: str) -> RefBinding:
        return CallerBinding(self.bind_tag(name), self.visible_name(name))

    def visible_name(self, name: str) -> str:
        frame = self.current_frame()
        if frame is None:
            return name

        for parameter_name, parameter_value in frame.parameters.items():
            if parameter_value == name:
                return parameter_name
        return name

    def branch_listing(self) -> list[BranchListingEntry]:
        frame = self.current_frame()
        if frame is None:
            return sorted(
                [
                    BranchListingEntry(name, name == self.HEAD, name == "main")
                    for name in self.branches
                ],
                key=lambda entry: (entry.name != "main", not entry.protected, entry.name)
            )

        entries: list[BranchListingEntry] = []
        if "main" in frame.bindings and frame.bindings["main"].is_branch():
            entries.append(self._branch_binding_entry("main", frame.bindings["main"]))

        branch_bindings: list[BranchListingEntry] = []
        for name, binding in frame.bindings.items():
            if name == "main" or not binding.is_branch():
                continue
            branch_bindings.append(self._branch_binding_entry(name, binding))

        entries.extend(sorted(branch_bindings, key=lambda entry: (not entry.protected, entry.name)))

        entries.extend(sorted([
            BranchListingEntry(name, name == self.HEAD)
            for name in frame.branches
        ], key=lambda entry: entry.name))

        return entries

    def _branch_binding_entry(self, name: str, binding: RefBinding) -> BranchListingEntry:
        return BranchListingEntry(
            self.visible_name(name),
            name == self.HEAD,
            binding.is_protected(),
            binding.branch_binding_chain(),
        )

    def tag_listing(self) -> list[TagListingEntry]:
        frame = self.current_frame()
        if frame is None:
            return sorted(
                [
                    TagListingEntry(name, commit)
                    for name, commit in self.tags.items()
                ],
                key=lambda entry: entry.name,
            )

        entries: list[TagListingEntry] = []
        for name, binding in frame.bindings.items():
            if binding.is_tag():
                entries.append(self._tag_binding_entry(name, binding))

        entries.extend(
            TagListingEntry(name, commit)
            for name, commit in frame.tags.items()
        )

        return sorted(entries, key=lambda entry: (not entry.bound, entry.name))

    def _tag_binding_entry(self, name: str, binding: RefBinding) -> TagListingEntry:
        return TagListingEntry(
            self.visible_name(name),
            binding.resolve(),
            True,
            binding.tag_binding_chain(),
        )

    def protected_caller_names(self) -> set[str]:
        names = {"main", self.HEAD}
        frame = self.current_frame()
        if frame is not None:
            names.add(frame.caller_head)
        return names

    def visible_commit_annotations(self) -> dict[Commit, list[str]]:
        annotations: dict[Commit, list[str]] = {}

        def add(commit: Commit, label: str) -> None:
            annotations.setdefault(commit, []).append(label)

        frame = self.current_frame()
        if frame is None:
            for name, commit in self.branches.items():
                label = f"HEAD -> {name}" if name == self.HEAD else f"branch:{name}"
                if name == "main":
                    label += "!"
                add(commit, label)
            for name, commit in self.tags.items():
                add(commit, f"tag:{name}")
            return annotations

        if "main" in frame.bindings:
            self._add_binding_annotation(annotations, "main", frame.bindings["main"])

        for name, commit in frame.branches.items():
            label = f"HEAD -> {name}" if name == self.HEAD else f"branch:{name}"
            add(commit, label)

        for name, commit in frame.tags.items():
            add(commit, f"tag:{name}")

        commit_parameter_names = {
            value: name
            for name, value in frame.parameters.items()
            if value in frame.bindings and isinstance(frame.bindings[value], CommitBinding)
        }

        for name, binding in frame.bindings.items():
            if name == "main":
                continue
            if isinstance(binding, CommitBinding):
                add(binding.resolve(), f"param:{commit_parameter_names.get(name, self.visible_name(name))}")
                continue
            self._add_binding_annotation(annotations, name, binding)

        return annotations

    def visible_commits(self) -> set[Commit]:
        return set(self.visible_commit_annotations())

    def _add_binding_annotation(
            self,
            annotations: dict[Commit, list[str]],
            name: str,
            binding: RefBinding,
    ) -> None:
        if binding.is_branch():
            visible = self.visible_name(name)
            label = f"HEAD -> {visible}" if name == self.HEAD else f"branch:{visible}"
            if binding.is_protected():
                label += "!"
            annotations.setdefault(binding.resolve(), []).append(label)
            return
        if binding.is_tag():
            annotations.setdefault(binding.resolve(), []).append(f"tag:{self.visible_name(name)}")

    def _binding(self, name: str) -> RefBinding | None:
        frame = self.current_frame()
        if frame is None:
            return None
        return frame.bindings.get(name)
