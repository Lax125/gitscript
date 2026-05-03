git tag root  # 0

git checkout -b input
git commit -m "
git tag original_input
git checkout -b reverted_input root
git revert root..input

# Example input: "cba"
#
# (root)
#   0  <-  'c'  <-  'b'  <-  'a' (input, original_input)
#      <- -'a'  <- -'b'  <- -'c' (reverted_input)

git branch num_differences root
git branch difference root
<<<<<<< input
    git checkout difference
    git reset root
    git merge input
    git merge reverted_input
    git merge root -s !=

    <<<<<<< difference
        git checkout num_differences
        git merge difference
        git checkout difference
        git reset root
    =======
        # difference = -1, indicating characters match
        git checkout difference
        git reset root
    >>>>>>> root

    git checkout input
    git reset HEAD~1
    git checkout reverted_input
    git reset HEAD~1
=======
    # should never execute because reverted_input should be negative for each character
>>>>>>> reverted_input

git checkout -b check root
git cherry-pick num_differences
git merge root -s ==
git checkout -b message root
<<<<<<< check
    git commit -m " is a palindrome."
    git checkout check
    git reset root
=======
    git commit -m " is not a palindrome."
    git checkout check
    git reset root
>>>>>>> root

git checkout message
git cherry-pick root..original_input
git log root..message
