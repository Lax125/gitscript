# GitScript Language Specification

## Commit References

```text
<commit-ref> =
    HEAD
  | <branch-name>
  | <tag-name>
  | <commit-ref>~<non-negative-int>
  | <commit-ref>~<commit-ref>
  | (<commit-ref>)
```

### Semantics

* `HEAD` refers to the current branch's tip
* `<branch-name>` refers to that branch's tip
* `<tag-name>` refers to the commit at the specified tag
* `~n` moves `n` commits backwards
* `<ref>~n` is a runtime error if `<ref>` has fewer than `n` ancestors
* `<ref>~<ref>`:

  * evaluate RHS to get its value `n`
  * then compute `<ref>~n`
* `~` associates **right-to-left**

### Example

```gitscript
HEAD~(foo~1)
```

---

## Commit Ranges

```text
<commit-range> = <commit-ref>..<commit-ref>
```

### Semantics

`A..B` refers to all commits reachable from `B` (including `B`) but not reachable from `A`.

* If `A == B`, the range is empty
* Order is always defined relative to traversal from `B` backwards

---

## Commands

### `git branch`

```gitscript
git branch <name> [<commit-ref>]
```

Creates a new branch.

* If a commit is specified, the branch points there
* Otherwise, it points to the current commit

---

### `git branch -d`

```gitscript
git branch -d [<branch-name>]...
```

Deletes the specified branches.

---

### `git tag`

```gitscript
git tag <name>
```

Creates a named reference to the current commit.

---

### `git tag -d`

```gitscript
git tag -d [<tag-name>]...
```

Deletes the specified tags.

---

### `git checkout`

```gitscript
git checkout <branch-name>
git checkout -b <branch-name> [<commit-ref>]
```

* Switch active branch
* `-b` creates the branch first

---

### `git commit` (integer)

```gitscript
git commit [--amend] [-m <int>]
```

* Creates a new commit with an integer value
* If `-m` is omitted, reads from stdin
* `--amend` uses the current commit's parent

---

### `git commit -m "` (string input)

```gitscript
git commit -m "
```

* Reads a string from stdin
* Stores it as a sequence of commits (one per character)
* Characters are stored in **reverse order** (last character closest to HEAD)
* `--amend` is not allowed for string commits

---

### `git commit -m "string"`

Same as above, but inline.

---

### `git reset`

```gitscript
git reset <commit-ref>
```

Moves the current branch to the specified commit.

---

### `git cherry-pick`

```gitscript
git cherry-pick <commit-ref> [-s <strategy>]
git cherry-pick <commit-range> [-s <strategy>]
```

Creates new commits from existing commits.

* `<commit-ref>`: creates a new commit using the referenced commit and the selected strategy
* `<commit-range>`: replays commits **from oldest to newest**, preserving order

Strategies combine:

* **ours** = current `HEAD` value
* **theirs** = the next referenced commit value

For a range with a strategy, the strategy is applied as a reduction. Each new commit becomes the next `ours` value.

Example: cherry-picking values `[1, 2, 3]` onto a current value of `5` with `-s=+` creates commits `[6, 8, 11]`.

#### Value Selection

* `theirs` (default): commit `theirs`
* `ours`: commit `ours`

#### Arithmetic

* `+`
* `-`
* `*`
* `/` (integer division)
* `%`

#### Comparison (returns `0` or `1`)

* `>`
* `<`
* `>=`
* `<=`
* `==`
* `!=`

---

### `git merge`

```gitscript
git merge [-s <condition>] [<label>]
git merge --continue [<label>]
git merge --abort [<label>]
```

Controls merge-conflict blocks.

`git merge` starts the following merge-conflict block. `-s` selects the condition used to choose between the two sides.

The optional positional `<label>` names the merge block. This uses the argument position that real Git uses for the commit being merged.

If no condition is specified, the condition is `==`.

#### Conditions

Conditions are separate from value-combining cherry-pick strategies:

* `>`: first commit value is greater than second commit value
* `<`: first commit value is less than second commit value
* `>=`: first commit value is greater than or equal to second commit value
* `<=`: first commit value is less than or equal to second commit value
* `==`: first commit value equals second commit value
* `!=`: first commit value does not equal second commit value
* `is`: both commit references resolve to the exact same commit object

#### Execution

```gitscript
git merge [-s <condition>] [<label>]
<<<<<<< A
    ...
=======
    ...
>>>>>>> B
```

1. Evaluate `A` and `B` to commits.
2. If `A <condition> B` is true, run the top block.
3. Otherwise, run the bottom block.
4. Reaching the end of the selected block exits the control structure.
5. `git merge --continue` jumps back to step 1 of the current control structure.
6. `git merge --abort` skips to the end of the current control structure immediately.
7. `git merge --continue <label>` jumps back to the matching labeled merge block, even through nested merge blocks.
8. `git merge --abort <label>` skips to the end of the matching labeled merge block, even through nested merge blocks.

This makes loops explicit: use `git merge --continue` when a selected side should repeat. One-shot conditional behavior is the default because falling out of a side exits.

---

### `git revert`

```gitscript
git revert <commit-ref>
git revert <commit-range>
```

* `<commit-ref>`: creates a commit with the **negated value**
* `<commit-range>`:

  * iterates commits from newest to oldest
  * appends commits with **negated values**

---

### `git rebase`

```gitscript
git rebase <commit-ref>
```

Replays commits from the current branch onto the target commit.

* Only values are replayed
* Original control flow is not preserved

---

### `git show`

```gitscript
git show [<commit-ref>]
```

Prints the value of a commit (default: `HEAD`).

---

### `git log`

```gitscript
git log [-n <non-negative-int>] [--reverse] <commit-ref>
git log [-n <non-negative-int>] [--reverse] <commit-range>
```

Prints characters from commits.

* `<commit-ref>`: all commits reachable from that commit
* `<commit-range>`: commits in the specified range

Traversal is:

* default: newest to oldest
* `--reverse`: oldest to newest

Each commit value is interpreted as a character.

---

### `git rev-list`

```gitscript
git rev-list [-n <non-negative-int>] [--reverse] <commit-ref>
git rev-list [-n <non-negative-int>] [--reverse] <commit-range>
```

Prints commit values (integers), one per line.

* `<commit-ref>`: all reachable commits
* `<commit-range>`: commits in the range

---

## Control Flow (Merge Conflicts)

GitScript uses merge conflict syntax for control flow:

```gitscript
git merge [-s <condition>] [<label>]
<<<<<<< A
    ...
=======
    ...
>>>>>>> B
```

### Execution Rules

Merge-conflict blocks are controlled by `git merge`.

* `git merge` starts the block and chooses the condition
* `git merge --continue` repeats the block
* `git merge --abort` exits the block
* `git merge --continue <label>` repeats the matching labeled block
* `git merge --abort <label>` exits the matching labeled block
* The conflict markers provide the two commit references compared by the condition

---

## Chaotic Addressing

Commit references can depend on values of other commits:

```gitscript
HEAD~(foo~2)
```

This enables:

* dynamic indexing
* pointer-like behavior
* self-modifying access patterns

---

## Garbage Collection

GitScript automatically removes commits that are no longer reachable from any:

* branch
* tag

This happens implicitly after operations like:

* `reset`
* `rebase`

---

## Notes

* Division by zero is undefined behavior
* Negative offsets are runtime errors
* Infinite loops are easy to create (and expected)

---

## Philosophy

GitScript treats Git history as a computational model:

* time = memory
* branches = variables
* commits = values
* conflicts = control flow

Programs are less about *what* happens, and more about *how history evolves*.
