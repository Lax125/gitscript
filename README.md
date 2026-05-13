# GitScript

GitScript is an esoteric programming language where statements look like Git commands and control flow looks like merge conflicts.

Instead of variables or a stack, GitScript operates on a persistent **commit history**, where each commit stores an integer value.
Branches act as pointers into this history, and computation happens by creating, moving, and combining commits.

For the full language reference, see [docs/spec.md](docs/spec.md).

---

## Core Idea

* **Commits** store constant integer values.
* **Branches** act as variables by pointing to commits. Just like in Git, they can be checked out, committed to, reset, and rebased.
* **Tags** point to specific commits and cannot be moved.
* **History** acts as memory.
* **Merge conflicts** act as control flow. Instead of having separate structures for `if-else` and `while`, GitScript combines the two into an `if-else`
  statement that can be repeated (like continuing a while loop) or exited early.

The initial state consists of a single commit with value `0` on the `main` branch.

---

## Installation and Usage

From the repository root, install GitScript in editable mode:

```sh
pip install -e .
```

After installation, run a GitScript file:

```sh
gitscript ./examples/hello_world.gs
```

Start the REPL by running `gitscript` with no filename:

```sh
gitscript
```

Run a file and then keep exploring the resulting repository in the REPL:

```sh
gitscript -i ./examples/hello_world.gs
```

In `-i` mode, relative `git pull` and `git clone` paths in the REPL continue to resolve from the script's directory.

Open a live PyVis commit graph while running:

```sh
gitscript -v ./examples/hello_world.gs
```

The visual graph is zoomable and pannable. It updates as commits and refs change.

Inside the REPL, type GitScript commands one at a time. Use `quit` or `exit` to leave.

---

## Examples

### Hello World

```gitscript
git tag root
git commit -m "Hello, World!"
git log root..HEAD
```

Outputs:

```text
Hello, World!
```

---

### Countdown Loop

```gitscript
git checkout -b counter
git commit 3

git checkout -b one
git commit 1

git checkout counter
git merge -s gt
<<<<<<< counter
    git show
    git cherry-pick one -s=sub
    git merge --continue
=======
    git show
>>>>>>> main
```

Outputs:

```text
3
2
1
0
```

### Collatz
```gitscript
git commit 1
git tag one

# Apply 3n + 1 to current branch if odd, or n/2 if even
git config alias.apply_collatz !'
  git checkout -b zero
  git commit 0
  git checkout -b one
  git commit 1
  git checkout -b two
  git commit 2
  git checkout -b three
  git commit 3
  
  git checkout -b remainder main
  git cherry-pick two -s=mod
  git checkout main
  git merge -s=eq
  <<<<<<< remainder
    git cherry-pick two -s=div
  =======
    git cherry-pick three -s=mul
    git cherry-pick one -s=add
  >>>>>>> zero
'

git commit 27  # initial number
git merge -s=gt
<<<<<<< HEAD
  git show
  git apply_collatz
  git merge --continue
=======
  git show
>>>>>>> one
```

Outputs:

```text
27
82
41
(...several lines...)
8
4
2
1
```

## Philosophy

GitScript treats Git history as a computational model:

* time = memory
* branches = variables
* commits = values
* conflicts = control flow

Programs are less about *what* happens, and more about *how history evolves*.
