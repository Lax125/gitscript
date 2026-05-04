git tag root

git checkout -b space root
git commit -m " "

git checkout -b input root
git commit -m "  # sentence to reverse

git branch reversed root
git branch word_start input
git checkout -b word_end word_start

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

git log root..reversed
