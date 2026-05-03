git tag root

git checkout -b input
git commit -m "  # sentence to reverse

git checkout -b one root
git commit -m 1
git checkout -b space root
git commit -m " "

git branch index root
git branch spaces root
git branch count root
git branch current root

# Record the history depths of every space in the input.
git merge -s is
<<<<<<< input~index
    git merge --abort
=======
    git checkout current
    git reset input~index

    git merge -s ==
    <<<<<<< current
        git checkout spaces
        git cherry-pick index
        git checkout count
        git cherry-pick one -s=+
    =======
        git merge --abort
    >>>>>>> space

    git checkout index
    git cherry-pick one -s=+
    git merge --continue
>>>>>>> root

# The final fencepost is the length of the input.
git checkout spaces
git cherry-pick index
git checkout count
git cherry-pick one -s=+

git branch output root
git branch depth count
git branch next_depth root
git branch start root
git branch end root
git branch real_start root

# Walk each pair of fenceposts. Later words are committed on top of earlier
# output, which reverses word order because logs read from HEAD backward.
git merge -s >
<<<<<<< depth
    git checkout next_depth
    git reset depth
    git cherry-pick one -s=-

    git checkout start
    git reset spaces~depth
    git checkout end
    git reset spaces~next_depth

    git checkout real_start
    git reset start
    git merge -s is
    <<<<<<< start
        git merge --abort
    =======
        git checkout real_start
        git cherry-pick one -s=+
    >>>>>>> root

    git checkout output
    git cherry-pick input~end..input~real_start

    git merge -s is
    <<<<<<< end
        git checkout depth
        git reset root
    =======
        git checkout output
        git cherry-pick space
        git checkout depth
        git reset next_depth
    >>>>>>> spaces

    git merge --continue
=======
    git merge --abort
>>>>>>> root

git log root..output
