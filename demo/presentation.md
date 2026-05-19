# GitScript Demo Script

Audience: people who already know Git and programming.

Goal: show that GitScript is not "Git automation"; it is a toy language where Git-shaped state is the runtime model.

Setup before presenting:

```sh
pip install -e .
```

Run snippets either in the REPL:

```sh
gitscript
```

or by putting them in a temporary `.gs` file and running:

```sh
gitscript path/to/file.gs
```

---

## 1. Opening

Say:

> GitScript is an esoteric programming language where commits are values, branches are variables, history is memory, and merge conflicts are control flow.

Run:

```gitscript
git init
git tag root
git commit -m "Hello, GitScript!"
git log root..HEAD
```

Expected output:

```text
Hello, GitScript!
```

Point out:

* `git commit -m` commits one character per commit
* `git log <range>` prints those commits back as text
* the null root commit is avoided by tagging `root`

---

## 2. Branches Are Variables

Say:

> A branch is a mutable pointer to a commit. That makes it close enough to a variable to be dangerous.

Run:

```gitscript
git init
git checkout -b x
git commit 40
git checkout -b y main
git commit 2
git checkout x
git cherry-pick y -s=add
git show
git branch
```

Expected output includes:

```text
42
```

Point out:

* `git cherry-pick y -s=add` combines the current branch tip with `y`
* `git branch` is diagnostic output and shows visible branch state
* branch names are consistently highlighted in the terminal

---

## 3. History Is Memory

Say:

> A branch tip is one value, but the whole branch history is an addressable list.

Run:

```gitscript
git init
git tag root
git commit 10
git commit 20
git commit 30
git show HEAD
git show HEAD^
git show HEAD~2
git rev-list --reverse root..HEAD
```

Expected output:

```text
30
20
10
10
20
30
```

Point out:

* `^` is `~1`
* `~N` walks ancestors
* `rev-list` exposes history as numbers

---

## 4. Clone a Prepared Loop

Say:

> The next example needs a few setup branches. Rather than making you watch me type them, `git clone` copy-pastes a prepared GitScript file and starts it from a clean repo.

Run:

```gitscript
git clone demo/countdown_setup.gs
git merge -s gt countdown
<<<<<<< counter
    git show
    git cherry-pick one -s=sub
    git merge --continue countdown
=======
    git show
>>>>>>> main
```

Expected output:

```text
3
2
1
0
```

Point out:

* `git merge -s gt` asks whether the first marker's commit value is greater than the second marker's commit value
* top block = then, bottom block = else
* `git merge --continue countdown` loops to the start of that merge block
* `git merge --abort countdown` would jump out early

---

## 5. Visualize the Commit Graph

Say:

> Because the runtime is history, a graph view is a debugger.

Run:

```gitscript
git clone demo/graph_setup.gs
git log --graph --all
git branch
git tag
```

Point out:

* `--all` includes all visible refs
* branch, tag, and commit metadata are diagnostic output
* unrelated-looking histories can exist because branches can be reset or created from old commits

---

## 6. Functions and Scoped Branches

Say:

> Functions get their own branch and tag scope. The caller's current branch is available as protected `main`, a little like `self`.

Run:

```gitscript
git init
git config alias.bump -p target -i amount '!
    git checkout target
    git commit amount
    git branch scratch
    git branch
    pause
'

git checkout -b score
git bump score 7
git show score
git branch
```

Expected output includes:

```text
7
```

Point out:

* `score` is passed as a protected branch parameter
* local `scratch` exists only inside the function call
* `git branch` inside the function shows bindings back to the caller

---

## 7. Imports: Pull and Push

Say:

> GitScript imports are deliberately explicit. A file exposes aliases with `git push`; another file imports only named aliases with `git pull`.

Run:

```gitscript
git init
git pull demo/math_lib.gs inc add_one
git inc
git show
git add_one main
git show
git config
```

Expected output includes:

```text
1
2
```

Point out:

* `math_lib.gs` pushes only `inc` and `add_one`
* `git pull` requires explicit names
* `git config` shows visible shortforms and functions
* imported private dependencies do not leak into the public namespace

---

## 8. Strings Are Histories Too

Say:

> Strings are not a separate data type. They are ranges of character-valued commits.

Run:

```gitscript
git init
git tag root
git commit -m """GitScript
speaks
history."""
git log root..HEAD
git rev-list --reverse root..HEAD
```

Point out:

* multiline strings are committed as character histories
* `git log` interprets values as characters
* `git rev-list` shows the same data as integers

---

## 9. Real Examples

Say:

> These are still intentionally weird, but they are complete programs.

Run one or two depending on time:

```sh
gitscript ./examples/fibonacci.gs
```

Input:

```text
8
```

Run:

```sh
gitscript ./examples/collatz.gs
```

Input:

```text
6
```

Run:

```sh
gitscript ./examples/reverse_words.gs
```

Input:

```text
hello from git history
```

Mention if time:

* `examples/primes.gs` demonstrates importing helper aliases
* `examples/word_sort.gs` leans into chaotic addressing
* `examples/quine.gs` prints exactly itself

---

## 10. Closing

Say:

> GitScript asks: what if Git's data model were the machine? It is terrible as a practical language, but surprisingly expressive as a lens for history, scope, and control flow.

Good final commands:

```gitscript
git init
git commit -m "Everything is a commit."
git log --graph
```

