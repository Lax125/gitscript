# GitScript

GitScript is an esoteric programming language where programs look like Git commands and control flow looks like merge conflicts.

Instead of variables or a stack, GitScript operates on a persistent **commit history**, where each commit stores an integer value. Branches act as pointers into this history, and computation happens by creating, moving, and combining commits.

For the full language reference, see [docs/spec.md](docs/spec.md).

---

## Core Idea

* **Commits** store integer values
* **Branches** point to commits (like variables)
* **History** acts as memory
* **Merge conflicts** act as control flow

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
git commit -m 3

git checkout -b one
git commit -m 1

git checkout counter
git merge -s >
<<<<<<< counter
    git show
    git cherry-pick one -s=-
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

## Philosophy

GitScript treats Git history as a computational model:

* time = memory
* branches = variables
* commits = values
* conflicts = control flow

Programs are less about *what* happens, and more about *how history evolves*.
