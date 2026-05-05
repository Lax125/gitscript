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

## Identifiers

Branch names, tag names, alias names, and parameter names are intentionally simpler than real Git refs.

Valid names:

* may contain only `A-Z`, `a-z`, `0-9`, `-`, `_`, and `/`
* may not start with `-`
* may not be `HEAD`, because `HEAD` always means the current branch tip
* may not be a GitScript keyword, operator, merge condition, or cherry-pick strategy

For example, `git`, `commit`, `merge`, `is`, and `max` are not valid branch or tag names.

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
git branch
git branch <name> [<commit-ref>]
```

With no arguments, lists branches visible in the current execution frame.

With arguments, creates a new branch.

* If a commit is specified, the branch points there
* Otherwise, it points to the current commit

#### Listing Branches

`git branch` prints one line per visible branch.

The listing includes:

* branches owned by the current frame
* branch bindings explicitly passed into the current frame
* the protected `main` binding inside a function frame

Branches not visible in the current frame are not listed.

The current branch is marked with `*` in the first column, matching Git. Non-current branches use a space in that column.

Protected branches are marked with `!` after the branch name. A protected branch cannot be deleted in the current frame. This includes global `main`, function-frame `main`, and branches passed through `-p`.

Branch bindings are shown with `->`. The left side is the name visible in the current frame, and the right side describes the branch in the caller frame that it binds to. Bindings can point through multiple caller frames; each layer is shown from inner to outer.

Example at global scope:

```text
   main !
 * feature
```

Example inside a function called from branch `feature`, with an unprotected `-b output`, protected `-p owner`, and `main` bound to the caller's current branch:

```text
   main ! -> caller:feature
 * scratch
   output -> caller:result
   owner ! -> caller:main
```

Example inside nested function calls:

```text
   main ! -> caller:worker -> caller:feature
   target -> caller:output -> caller:result
```

The exact caller labels are diagnostic text only. The semantic requirements are that the listing identifies whether a visible branch is protected and whether it is a binding to a branch outside the current frame.

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
git commit [--amend] [<int>]
```

* Creates a new commit with an integer value
* If the integer is omitted, reads an integer literal from stdin
* `--amend` uses the current commit's parent
* `-m` is not used for integer commits

---

### `git commit -m` (string input)

```gitscript
git commit -m
```

* Reads a single-line string from stdin
* Stores it as a sequence of commits (one per character)
* Characters are stored in **reverse order** (last character closest to HEAD)
* `--amend` is not allowed for string commits
* `-m` always selects string commit mode

---

### `git commit -m "string"`

Same as above, but inline. A string value can also be supplied with `-m=`.

---

### `git commit -m """string"""`

```gitscript
git commit -m """this is a multiline string
and " does not need to be escaped"""

git commit -m """
this is also a multiline string
but with a newline at the start and at the end
"""
```

Stores a literal multiline string as a sequence of commits, one per character.

Triple-quoted strings:

* may span multiple source lines
* may contain unescaped `"` characters
* may contain `&&` without creating statement separators
* may be written with `-m """..."""` or `-m="""..."""`
* do not allow `--amend`

The string contains exactly the characters between the opening and closing `"""`.

---

### `git reset`

```gitscript
git reset <commit-ref>
```

Moves the current branch to the specified commit.

---

### `git cherry-pick`

```gitscript
git cherry-pick <commit-ref> [-s ltstrategy>]
git cherry-pick <commit-range> [-s ltstrategy>]
```

Creates new commits from existing commits.

* `<commit-ref>`: creates a new commit using the referenced commit and the selected strategy
* `<commit-range>`: replays commits **from oldest to newest**, preserving order

Strategies combine:

* **ours** = current `HEAD` value
* **theirs** = the next referenced commit value

For a range with a strategy, the strategy is applied as a reduction. Each new commit becomes the next `ours` value.

Example: cherry-picking values `[1, 2, 3]` onto a current value of `5` with `-s=add` creates commits `[6, 8, 11]`.

#### Value Selection

* `theirs` (default): commit `theirs`
* `ours`: commit `ours`
* `min`: commit the lesser of `ours` and `theirs`
* `max`: commit the greater of `ours` and `theirs`

#### Arithmetic

* `add`
* `sub`
* `mul`
* `div` (integer division)
* `mod`

#### Comparison (returns `0` or `1`)

* `gt`
* `lt`
* `gte`
* `lte`
* `eq`
* `neq`

---

### `git merge`

```gitscript
git merge [-s ltcondition>] [<label>]
git merge --continue [<label>]
git merge --abort [<label>]
```

Controls merge-conflict blocks.

`git merge` starts the following merge-conflict block. `-s` selects the condition used to choose between the two sides.

The optional positional `<label>` names the merge block. This uses the argument position that real Git uses for the commit being merged.

If no condition is specified, the condition is `eq`.

#### Conditions

Conditions are separate from value-combining cherry-pick strategies:

* `gt`: first commit value is greater than second commit value
* `lt`: first commit value is less than second commit value
* `gte`: first commit value is greater than or equal to second commit value
* `lte`: first commit value is less than or equal to second commit value
* `eq`: first commit value equals second commit value
* `neq`: first commit value does not equal second commit value
* `is`: both commit references resolve to the exact same commit object

#### Execution

```gitscript
git merge [-s ltcondition>] [<label>]
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
git log [-n <non-negative-int>] [--reverse] [--oneline] <commit-ref>
git log [-n <non-negative-int>] [--reverse] [--oneline] <commit-range>
```

Prints characters from commits.

* `<commit-ref>`: all commits reachable from that commit
* `<commit-range>`: commits in the specified range

Traversal is:

* default: newest to oldest
* `--reverse`: oldest to newest

By default, `git log` prints a trailing newline after the characters. `--oneline` omits that trailing newline, which is useful for prompts before `git commit` and `git commit -m` read from stdin.

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
git merge [-s ltcondition>] [<label>]
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

Expanding a shortform must produce exactly one statement. It cannot produce multiple statements with `&&`.

For example, this definition is accepted:

```gitscript
git config alias.ci 'commit'
```

This call expands to one statement:

```gitscript
git ci 20
```

This definition is also accepted, because shortforms are not validated when defined:

```gitscript
git config alias.abc 'commit 20 && git show'
```

But running it is an error:

```gitscript
git abc
```

The expanded text contains two statements, so it cannot be used as a shortform expansion.

Example:

```gitscript
git config alias.cp 'cherry-pick'
git cp main -s=max
```

The second line is parsed as:

```gitscript
git cherry-pick main -s=max
```

Alias substitution can happen multiple times. If the replacement fragment begins with another shortform or function name, that name is expanded too. The final expanded result must still be one statement.

No validation is performed when the shortform is defined. The fragment does not need to form a valid statement at definition time. It can still expand to a statement that defines another shortform or function, or to a statement that commits a multiline string.

Alias expansion happens while parsing the command being executed, using aliases that have already been executed. Aliases defined later in the program are not visible earlier in the program.

### Functions

```gitscript
git config alias.function_name [-i <name>]... [-s ltname>]... [-l <name>]... [-b <name>]... [-p <name>]... [-t <name>]... [-r <name>]... [-c <name>]... [-o <name>]... '![statement]...'
```

Defines a function. A function body is an ordered list of zero or more statements. When `git function_name` is executed, GitScript executes those statements in order.

The body begins after the `!` and ends at the closing single quote. The first statement can appear on the same line as `git config`, and the last statement can appear on the same line as the closing quote.

Example:

```gitscript
git config alias.dec '!
  git cherry-pick one -s=sub
  git show
'
```

This defines `git dec` as a two-statement function.

The same function can also be written with the first and last statements adjacent to the quotes:

```gitscript
git config alias.dec '!git cherry-pick one -s=sub && git show'
```

#### Function Body Validation

Function bodies are syntax-checked when the function is defined.

Each statement in a function body must:

* start with `git`, or
* be `exit`

Built-in `git` statements in a function body must conform to the same syntax as top-level built-in statements. This includes command options, ref syntax, merge conditions, cherry-pick strategies, and multiline string syntax.

Parameter references are checked against the function's declared parameters. A parameter can only be used where its declared type is valid:

* `-i` parameters can be used where integer literals are accepted
* `-s` parameters can be used where string literals are accepted
* `-l` parameters can be used where a new branch or tag name is accepted
* `-b` parameters can be used where an existing unprotected branch name is accepted
* `-p` parameters can be used where an existing protected branch name is accepted
* `-t` parameters can be used where an existing tag name is accepted
* `-r` parameters can be used where commit references are accepted
* `-c` parameters can be used where merge conditions are accepted
* `-o` parameters can be used where cherry-pick strategies are accepted

This validation catches some errors before the function is ever called. For example, deleting a protected branch parameter is invalid:

```gitscript
git config alias.bad -p target '!
  git branch -d $target
'
```

Function body validation is syntax and type validation only. It does not prove that runtime refs exist, that arithmetic is safe, that loops terminate, or that a valid runtime path reaches every statement.

### Parameters

Function definitions can declare named parameters before the function body:

```gitscript
git config alias.foo -i my_int -s my_string '!
  git commit $my_int
  git commit -m "$my_string"
'
```

Parameter names use the same syntax rules as branch and tag names.

Function calls provide arguments positionally:

```gitscript
git foo 3 "hello"
```

Each call creates one call-stack frame containing the parameter values, local branches, and local tags for that function invocation. Parameter references resolve against the current frame. When the function returns, that frame is removed.

Parameters are referenced with `$<name>`:

```gitscript
$my_int
$my_string
```

A parameter reference can appear anywhere a value of that parameter's type is expected.

Parameter types:

* `-i <name>`: integer literal. `true` and `false` are accepted as integer literals with values `1` and `0`
* `-s ltname>`: string literal
* `-l <name>`: label. The argument must be a valid name that does not currently refer to an existing branch or tag in the caller's frame. This is useful for functions that create branches or tags in the caller's frame.
* `-b <name>`: existing unprotected branch. The argument must name a branch that exists when the function is called. `main` and the caller's current branch cannot be passed as `-b`.
* `-p <name>`: existing protected branch. The argument must name a branch that exists when the function is called. `main` and the caller's current branch can be passed as `-p`, and the branch cannot be deleted through the parameter inside the function.
* `-t <name>`: existing tag. The argument must name a tag that exists when the function is called.
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

### Branch and Tag Scope

Branches and tags are scoped to the current execution frame.

At global scope, branches and tags are global. Inside a function call, branch and tag names refer only to refs in that function's current call frame, plus any refs explicitly passed into the function.

`main` is a protected branch name.

* At global scope, `main` is the initial branch and cannot be deleted.
* Inside a function call, `main` is a protected alias for the caller's previous branch, similar to `self` in Python methods.
* Function-local code can `checkout`, `commit`, `reset`, and otherwise operate on `main` to modify the caller's branch intentionally.
* A function cannot create, delete, or shadow `main`.

Refs created inside a function shadow, but do not overwrite or modify, global refs with the same name.

When a function returns normally or exits early with `exit`, all branches and tags created in that function call are removed automatically.

This means a function cannot access an arbitrary global branch or tag by naming it directly:

```gitscript
git branch branch1

git config alias.example '!
  git checkout branch1  # looks for local branch1, not global branch1
'
```

The same rule applies to tags:

```gitscript
git tag saved

git config alias.example '!
  git show saved  # looks for local saved, not global saved
'
```

To let a function use a branch or tag from its caller other than the caller's current branch, pass the name as a parameter:

```gitscript
git branch branch1

git config alias.example -b target '!
  git checkout $target
'

git example branch1
```

The `-b` parameter binds an existing unprotected branch from the caller's frame. Inside the function, `$target` refers to that bound caller branch, even if a local ref with the same literal name would otherwise be inaccessible.

`main` and the caller's current branch name cannot be passed to `-b` parameters, whether positionally or by named argument. The caller's current branch is already available inside the function as `main`.

Use `-p` for branch parameters that are allowed to refer to protected branches. A `-p` parameter can refer to `main` or the caller's current branch, and function-local code can `checkout`, `commit`, and `reset` through that parameter. It cannot delete the branch through that parameter.

Use `-t` to bind an existing tag from the caller's frame.

Use `-l` when a function needs a new label for a branch or tag it will create in the caller's frame. A `-l` argument is checked when the function is called and is valid only if it does not currently refer to any branch or tag in the caller's frame. Inside the function, creating `git branch $label` or `git tag $label` creates that ref in the caller's frame, not in the callee's temporary frame. This is similar in spirit to Python's `global`: the name is still introduced by the callee's code, but it belongs to the enclosing namespace.

Commit-ref parameters (`-r`) are evaluated in the caller's frame when the function is called, then behave as commit references inside the callee. This lets a caller pass `branch1~2` without exposing the caller's `branch1` name directly.

Nested function calls create nested frames. A branch or tag created in an outer function is not visible by name inside an inner function unless it is passed as a parameter to the inner function. In each nested call, `main` refers to that call's caller branch.

When a function returns, GitScript restores the caller's previous `HEAD`. Because `main` is protected inside the function, this restoration is valid even if the function deleted other local branches.

### Early Exit

`exit` leaves the current function immediately. If `exit` runs at global scope, it ends the program.

### Parameter Defaults and Named Arguments

Defaults are declared by assigning a literal value in the parameter declaration:

```gitscript
git config alias.foo -i count=1 -s message="ok" '!
  git commit $count
  git commit -m "$message"
'
```

Defaults make parameters optional from the right when calling positionally:

```gitscript
git foo
git foo 3
git foo 3 "done"
```

Defaults for `-l`, `-b`, `-p`, and `-t` parameters are checked when the function is called, the same as explicit arguments.

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
git commit 1 && git show
```

This is equivalent to:

```gitscript
git commit 1
git show
```

A merge-conflict control structure is one statement for this purpose. The `git merge [-s ltcondition>] [<label>]` line and its corresponding conflict markers and blocks stay together as a single statement, even though the statement spans multiple lines.

Lexically, newlines, `&&`, and merge-conflict markers are statement separators.

Conflict markers are forced to stay on their own physical lines. `&&` is not allowed before or after:

* `<<<<<<< <commit-ref>`
* `=======`
* `>>>>>>> <commit-ref>`

This means the inside of a conflict block can use `&&` between ordinary statements, but the marker lines themselves cannot share a line with anything else.

Example:

```gitscript
git merge -s gt loop
<<<<<<< counter
    git cherry-pick one -s=sub && git merge --continue loop
=======
    git merge --abort loop
>>>>>>> root
git show counter
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

* Division and modulo by zero are runtime errors
* Negative offsets are runtime errors
* Infinite loops are easy to create (and expected)

---
