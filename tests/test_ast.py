import unittest

from gitscript.ast import (
    AncestorRef,
    BranchRef,
    ConstantOffsetRef,
    DynamicOffsetRef,
    HeadRef,
    Ref,
    resolve,
)
from gitscript.commands import branch, checkout, commit, tag
from gitscript.repo import Repo


class RefTests(unittest.TestCase):
    def test_unknown_ref_type_raises_runtime_error(self):
        repo = Repo()

        with self.assertRaisesRegex(RuntimeError, "Unknown ref type"):
            resolve(Ref(), repo)

    def test_head_ref_resolves_current_branch_tip(self):
        repo = Repo()
        commit(repo, 7)

        self.assertIs(resolve(HeadRef(), repo), repo.branches["main"])
        self.assertEqual(resolve(HeadRef(), repo).value, 7)

    def test_branch_ref_resolves_branch_tip(self):
        repo = Repo()
        commit(repo, 3)
        branch(repo, "three")
        commit(repo, 8)

        resolved = resolve(BranchRef("three"), repo)

        self.assertIs(resolved, repo.branches["three"])
        self.assertEqual(resolved.value, 3)

    def test_branch_ref_can_resolve_tag(self):
        repo = Repo()
        commit(repo, 11)
        tag(repo, "eleven")
        commit(repo, 12)

        resolved = resolve(BranchRef("eleven"), repo)

        self.assertIs(resolved, repo.tags["eleven"])
        self.assertEqual(resolved.value, 11)

    def test_ancestor_ref_stores_base_ref(self):
        base = HeadRef()
        ref = AncestorRef(base)

        self.assertIs(ref.base, base)

    def test_constant_offset_ref_resolves_fixed_ancestor(self):
        repo = Repo()
        commit(repo, 10)
        commit(repo, 20)
        commit(repo, 30)

        ref = ConstantOffsetRef(HeadRef(), 2)
        resolved = resolve(ref, repo)

        self.assertEqual(ref.offset_value, 2)
        self.assertEqual(ref.offset(repo), 2)
        self.assertEqual(resolved.value, 10)

    def test_constant_offset_ref_clamps_at_root_commit(self):
        repo = Repo()
        commit(repo, 4)

        resolved = resolve(ConstantOffsetRef(HeadRef(), 99), repo)

        self.assertEqual(resolved.value, 0)
        self.assertIsNone(resolved.parent)

    def test_dynamic_offset_ref_uses_value_from_offset_expression(self):
        repo = Repo()
        commit(repo, 10)
        commit(repo, 20)
        commit(repo, 30)
        branch(repo, "numbers")

        checkout(repo, "main")
        commit(repo, 2)
        branch(repo, "offset")
        checkout(repo, "numbers")

        ref = DynamicOffsetRef(HeadRef(), BranchRef("offset"))
        resolved = resolve(ref, repo)

        self.assertIsInstance(ref, AncestorRef)
        self.assertIsInstance(ref.offset_expr, BranchRef)
        self.assertEqual(ref.offset(repo), 2)
        self.assertEqual(resolved.value, 10)

    def test_dynamic_offset_ref_rejects_negative_runtime_offset(self):
        repo = Repo()
        commit(repo, 1)
        branch(repo, "target")
        commit(repo, -1)
        branch(repo, "negative")
        checkout(repo, "target")

        ref = DynamicOffsetRef(HeadRef(), BranchRef("negative"))

        with self.assertRaisesRegex(RuntimeError, "Negative offset"):
            resolve(ref, repo)


if __name__ == "__main__":
    unittest.main()
