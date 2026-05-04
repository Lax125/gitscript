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

## Branch and Tag Names

Branch and tag names are intentionally simpler than real Git refs.

Valid names:

* may contain only `A-Z`, `a-z`, `0-9`, `-`, `_`, and `/`
* may not start with `-`
* may not be `HEAD`, because `HEAD` always means the current branch tip

Other Git words are ordinary names. For example, `git`, `commit`, and `merge` are valid branch or tag names.

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

## Integer Literals

Integer literals are decimal integers.

`true` and `false` are also integer literals:

* `true` = `1`
* `false` = `0`

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

### `git config`

```gitscript
git config commit.verbose <int>
git config merge.verbosity 0
git config merge.verbosity 1
git config merge.verbosity 2
```

Configures debug logging.

Debug logs are diagnostic output and are written separately from program output so commands like `git log`, `git show`, and `git rev-list` remain usable as program output.

#### `commit.verbose`

Default: `0`

When `commit.verbose` is nonzero, GitScript logs every new commit created by any process, including:

* `git commit`
* string commits, once per character commit
* `git cherry-pick`
* `git cherry-pick <commit-range>`, once per replayed commit
* `git revert`
* `git revert <commit-range>`, once per replayed commit
* `git rebase`, once per replayed commit

`git commit --amend` logs the replacement commit that is created.

Operations that only move references, such as `git reset`, `git branch`, `git checkout`, and `git tag`, do not create commits and therefore do not emit commit logs.

Each commit log entry includes enough information to identify:

* the active branch receiving the new commit
* the new commit's value
* the new commit's parent value, or that it has no parent
* the operation that created it

#### `merge.verbosity`

Default: `0`

Merge verbosity controls debug logging for merge-conflict control flow:

* `0`: no merge debug logging
* `1`: log when a merge block begins evaluating and log each conditional check
* `2`: log everything from `1`, plus merge continues and aborts

At verbosity `1`, each conditional-check log includes:

* the merge label, if present
* the condition
* the two resolved commit values
* whether the top or bottom block was selected

At verbosity `2`, continue and abort logs include:

* whether the signal is `continue` or `abort`
* the target label, if present
* the merge block that handles the signal

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
* `min`: commit the lesser of `ours` and `theirs`
* `max`: commit the greater of `ours` and `theirs`

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

This makes loops explicit: use `git merge --continue` when a selected side will repeat. One-shot conditional behavior is the default because falling out of a side exits.

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

### `exit`

```gitscript
exit
```

Exits the current execution block early.

* Inside a function, `exit` returns from that function immediately
* At global scope, `exit` ends the program immediately
* Inside a merge-conflict block, `exit` exits the surrounding function if one is active; otherwise it exits the global program
* `exit` is separate from `git merge --abort`, which exits only merge-conflict control structures

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

## Functions and Aliases

Functions and shortforms are defined with `git config alias.<name>`. They share one alias namespace. Defining `alias.<name>` replaces any previous shortform or function with that name.

Alias and function names use the same name rules as branches and tags.

### Shortforms

```gitscript
git config alias.shortform 'statement-fragment'
```

Defines a command shortform. After this config statement runs, a command beginning with `git shortform` is parsed as though it began with `git statement-fragment`.

Arguments after the shortform are appended to the substituted command.

Example:

```gitscript
git config alias.cp 'cherry-pick'
git cp main -s=max
```

The second line is parsed as:

```gitscript
git cherry-pick main -s=max
```

Alias substitution can happen multiple times. If the replacement fragment begins with another shortform or function name, that name is expanded too.

No validation is performed when the alias is defined. The fragment does not need to form a valid statement at definition time. It can even define another shortform or function when it is later expanded and executed.

Alias expansion happens while parsing the command being executed, using aliases that have already been executed. Aliases defined later in the program are not visible earlier in the program.

### Functions

```gitscript
git config alias.function_name [-i <name>]... [-s <name>]... [-l <name>]... [-r <name>]... [-c <name>]... [-o <name>]... '![statement]...'
```

Defines a function. A function body is an ordered list of zero or more statements. When `git function_name` is executed, GitScript executes those statements in order.

The body begins after the `!` and ends at the closing single quote. The first statement can appear on the same line as `git config`, and the last statement can appear on the same line as the closing quote.

Example:

```gitscript
git config alias.dec '!
  git cherry-pick one -s=-
  git show
'
```

This defines `git dec` as a two-statement function.

The same function can also be written with the first and last statements adjacent to the quotes:

```gitscript
git config alias.dec '!git cherry-pick one -s=- && git show'
```

### Parameters

Function definitions can declare named parameters before the function body:

```gitscript
git config alias.foo -i my_int -s my_string '!
  git commit -m $my_int
  git commit -m "$my_string"
'
```

Parameter names use the same syntax rules as branch and tag names.

Function calls provide arguments positionally:

```gitscript
git foo 3 "hello"
```

Each call creates one call-stack frame containing the parameter values for that function invocation. Parameter references resolve against the current frame. When the function returns, that frame is removed.

Parameters are referenced with `$<name>`:

```gitscript
$my_int
$my_string
```

A parameter reference can appear anywhere a value of that parameter's type is expected.

Parameter types:

* `-i <name>`: integer literal. `true` and `false` are accepted as integer literals with values `1` and `0`
* `-s <name>`: string literal
* `-l <name>`: tag or branch name. The name is not checked for existence when the function is called
* `-r <name>`: commit reference
* `-c <name>`: merge-conflict condition
* `-o <name>`: cherry-pick integer operator

Example:

```gitscript
git config alias.pick -r source -o strategy '!
  git cherry-pick $source -s=$strategy
'

git pick main max
```

The call executes as though the function body contained:

```gitscript
git cherry-pick main -s=max
```

Calling a function with the wrong number of positional arguments is a runtime error, unless missing arguments have defaults.

### Early Exit

`exit` leaves the current function immediately. If `exit` runs at global scope, it ends the program.

### Parameter Defaults and Named Arguments

Defaults are declared by assigning a literal value in the parameter declaration:

```gitscript
git config alias.foo -i count=1 -s message="ok" '!
  git commit -m $count
  git commit -m "$message"
'
```

Defaults make parameters optional from the right when calling positionally:

```gitscript
git foo
git foo 3
git foo 3 "done"
```

Named arguments use long option syntax derived from the parameter name:

```gitscript
git foo --message "done" --count 3
```

Named arguments make argument order irrelevant and can be mixed after positional arguments, as long as each parameter is supplied at most once:

```gitscript
git foo 3 --message "done"
```

This keeps function calls visually close to Git command options while avoiding a second parameter syntax.

---

## Statement Separators

Statements are normally separated by newlines. `&&` can be used anywhere a newline could separate statements:

```gitscript
git commit -m 1 && git show
```

This is equivalent to:

```gitscript
git commit -m 1
git show
```

A merge-conflict control structure is one statement for this purpose. The `git merge [-s <condition>] [<label>]` line and its corresponding conflict markers and blocks stay together as a single statement, even though the statement spans multiple lines.

Example:

```gitscript
git merge -s > loop
<<<<<<< counter
    git cherry-pick one -s=- && git merge --continue loop
=======
    git merge --abort loop
>>>>>>> root
&& git show counter
```

The final `git show counter` runs after the whole merge-conflict statement finishes.

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
