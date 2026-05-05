git tag root

# Space is the separator that marks word boundaries.
git checkout -b space root
git commit -m " "

# Read the sentence to reverse.
git checkout -b input root
git commit -m  # sentence to reverse

# word_start marks the start of the current word; word_end walks backward.
git branch reversed root
git branch word_start input
git checkout -b word_end word_start

# When a space or root is reached, append the word range to reversed.
git merge -s is
<<<<<<< word_end
    git checkout reversed
    git cherry-pick word_end..word_start
=======
    git merge -s ==
    <<<<<<< word_end
        git checkout reversed
        git cherry-pick word_end..word_start
        git cherry-pick space
        git checkout word_start
        git reset word_end~1
    ========
    >>>>>>> space
    git checkout word_end
    git reset HEAD~1
    git merge --continue
>>>>>>> root

# Print the rebuilt sentence with words in reverse order.
git log root..reversed
