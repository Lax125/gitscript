git tag root

# Read the candidate word, then keep a tag to the original input for output.
git checkout -b input
git commit -m
git tag original_input

# Build a mirrored walk by reverting every character commit.
git checkout -b reverted_input root
git revert root..input

# Example input: "aba"
#
# 0 (root) <- 'a' <- 'b' <- 'a' (input, original_input)
#          <- -'a' <- -'b' <- -'a' (reverted_input)
#
# The two walking branches eventually collide at root. A mismatch resets both
# walkers to root so the loop exits early.

git branch difference root

git merge -s is compare
<<<<<<< input
    # input and reverted_input point at the same commit, so every compared pair
    # matched or an earlier mismatch forced both branches to root.
    git merge --abort
=======
    git checkout difference
    git reset root
    git cherry-pick input
    git cherry-pick reverted_input -s=add

    git merge -s eq
    <<<<<<< difference
        # Characters match. Advance both walkers.
        git checkout input
        git reset HEAD~1
        git checkout reverted_input
        git reset HEAD~1
    =======
        # Mismatch. Mark the difference and force the outer loop to finish.
        git checkout difference
        git reset root
        git commit 1
        git merge --abort compare
    >>>>>>> root
    git merge --continue
>>>>>>> reverted_input

git merge -s eq
<<<<<<< difference
    git checkout -b message root
    git commit -m " is a palindrome."
=======
    git checkout -b message root
    git commit -m " is not a palindrome."
>>>>>>> root

git checkout message
git cherry-pick root..original_input

# The message branch now contains the original word plus the verdict.
git log root..message
