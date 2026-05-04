from gitscript.commit import Commit


class Repo:
    def __init__(self):
        root = Commit(0, None)

        self.branches = {"main": root}
        self.tags = {}
        self.HEAD = "main"
        self.commit_verbose = False
        self.merge_verbosity = 0

    def resolve(self, tag_or_branch_name: str) -> Commit:
        if tag_or_branch_name in self.tags:
            return self.tags[tag_or_branch_name]
        elif tag_or_branch_name in self.branches:
            return self.branches[tag_or_branch_name]
        else:
            raise RuntimeError(f"Unknown tag or branch: {tag_or_branch_name}")

    def has(self, tag_or_branch_name: str) -> bool:
        return tag_or_branch_name in self.tags or tag_or_branch_name in self.branches
