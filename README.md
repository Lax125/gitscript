# GitScript

GitScript is an esoteric programming language where programs look like Git commands and control flow looks like merge conflicts.

Instead of variables or a stack, GitScript operates on a persistent **commit history**, where each commit stores an integer value. Branches act as pointers into this history, and computation happens by creating, moving, and combining commits.

---

## 🧠 Core Idea

* **Commits** store integer values
* **Branches** point to commits (like variables)
* **History** acts as memory
* **Merge conflicts** act as control flow

The initial state consists of a single commit with value `0` on the `main` branch.

---

## 🚀 Examples

### Hello World

```
git commit --amend -m "Hello, World!"
git log
```

Outputs:

```
Hello, World!
```

---

### GCD (Euclidean Algorithm)

```
git checkout -b a
git commit   # input integer

git checkout -b b
git commit   # input integer

<<<<<<< a
    git checkout a
    git merge b -s=-
=======
    git checkout b
    git merge a -s=-
>>>>>>> b

git show
```

---

## 🔖 Commit References

```
<commit-ref> =
    HEAD
  | <branch-name>
  | <tag-name>
  | <commit-ref>~<non-negative-int>
  | <commit-ref>~<commit-ref>
  | (<commit-ref>)
```

### Semantics

* `HEAD` refers to the current branch’s tip
* `<branch-name>` refers to that branch’s tip
* `<tag-name>` refers to the commit at the specified tag
* `~n` moves `n` commits backwards
* `<ref>~<ref>`:

  * evaluate RHS → get its value `n`
  * then compute `<ref>~n`
* `~` associates **right-to-left**

### Example

```
HEAD~(foo~1)
```

---

## ↔️ Commit Ranges
```
<commit-range> = <commit-ref>..<commit-ref>
```

### Semantics

`<commit-ref>..<commit-ref>` refers to all commits that are reachable from the RHS commit (including itself), but
not reachable from the LHS commit. `A..A` refers to an empty range of commits.

---

## ⚙️ Commands

### `git commit` (integer)

```
git commit [--amend] [-m <int>]
```

* Creates a new commit with an integer value
* If `-m` is omitted, reads from stdin
* `--amend` uses the current commit’s parent

---

### `git commit -m "` (string input)

```
git commit -m "
```

* Reads a string from stdin
* Stores it as a **null-terminated sequence of commits**
* Internally:

  * first commit = `0`
  * followed by characters in reverse order

---

### `git commit -m "string"`

Same as above, but inline.

---

### `git branch`

```
git branch <name> [<commit-ref>]
```

Creates a new branch. If a commit is specified, it is created there. Otherwise, it is created at the current commit.

---

### `git branch -d`

```
git branch -d [<name>]...
```

Removes existing branches with the specified names.

---

### `git checkout`

```
git checkout <branch-name>
git checkout -b <branch-name> [<commit-ref>]
```

* Switch active branch
* `-b` creates the branch first, optionally at a specific commit. This is equivalent to
  `git branch <branch-name> [<commit-ref>]` followed by `git checkout <branch-name>`.

---

### `git reset`

```
git reset <commit-ref>
```

Moves the current branch to the specified commit.

---

### `git merge`

```
git merge <commit-ref> [-s <strategy>]
```

Combines values using a strategy.

#### Arithmetic

* `+` (default)
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

### `git cherry-pick`

TODO: adjust semantics
```
git cherry-pick <commit-ref>
git cherry-pick <commit-range>
```

Creates a new commit with the same value as the referenced commit.

---
### `git revert`

TODO: semantics
```
git revert <commit-ref>
git revert <commit-range>
```

---

### `git rebase`

```
git rebase <commit-ref>
```

Replays commits from the current branch onto the target commit.

* Only values are replayed
* Original control flow is not preserved

---

### `git tag`

```
git tag <name>
```

Creates a named reference to the current commit.

---

### `git tag -d`

```
git tag -d [<name>]...
```

Removes existing tags with the specified names.

---

### `git show`

```
git show [<commit-ref>]
```

Prints the value of a commit (default: `HEAD`).

---

### `git log`

TODO: Adjust semantics. If a single commit ref is given, the selected commits are all commits reachable from that
commit.`git log` should have the same behaviour as `git log HEAD`.
```
git log [-n <non-negative-int>] [--reverse] [<commit-ref>]
git log [-n <non-negative-int>] [--reverse] <commit-range>
```

Prints a string by:

1. Starting at the given commit
2. Traversing backwards
3. Converting values to characters
4. Stopping at:

   * value `0` (null terminator), or
   * root commit

---

### `git rev-list`

TODO: Semantics. This command should print out the integer value, line by line, of the commit(s) specified. If a single
commit ref is given, the selected commits are all commits reachable from that commit.
```
git rev-list [-n <non-negative-int>] [--reverse] <commit-ref>
git rev-list [-n <non-negative-int>] [--reverse] <commit-range>
```

---

## ⚔️ Control Flow (Merge Conflicts)

GitScript uses merge conflict syntax for control flow:

```
<<<<<<< A
    ...
=======
    ...
>>>>>>> B
```

### Execution Rules

1. Evaluate `A` and `B` to commits
2. Compare their values:

   * if `A > B`: run top block
   * if `A < B`: run bottom block
   * if equal: exit
3. Repeat (values are re-evaluated each time)

### Equivalent Model

```
while value(A) != value(B):
    if value(A) > value(B):
        run A block
    else:
        run B block
```

---

## 🧵 Strings

Strings are stored as linked commits:

```
0 → 'o' → 'l' → 'l' → 'e' → 'h'
```

* `0` = null terminator
* traversal is backwards (HEAD → parent → ...)

---

## 🌀 Chaotic Addressing

Commit references can depend on values of other commits:

```
HEAD~(foo~2)
```

This enables:

* dynamic indexing
* pointer-like behavior
* self-modifying access patterns

---

## 🧹 Garbage Collection

GitScript automatically removes commits that are no longer reachable from any:

* branch
* tag

This happens implicitly after operations like:

* `reset`
* `rebase`

---

## ⚠️ Notes

* Division by zero is undefined behavior
* Negative offsets are runtime errors
* Infinite loops are easy to create (and expected)

---

## 🧪 Philosophy

GitScript treats Git history as a computational model:

* time = memory
* branches = variables
* commits = values
* conflicts = control flow

Programs are less about *what* happens, and more about *how history evolves*.
