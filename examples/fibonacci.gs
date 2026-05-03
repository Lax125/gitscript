git tag root

git checkout -b remaining
git commit  # sequence length

git checkout -b one root
git commit -m 1

git branch sequence root
git branch a root
git branch b one
git branch next root

git merge -s >
<<<<<<< remaining
    git checkout sequence
    git cherry-pick a

    git checkout next
    git reset a
    git cherry-pick b -s=+

    git checkout a
    git reset b
    git checkout b
    git reset next

    git checkout remaining
    git cherry-pick one -s=-
    git merge --continue
=======
    git merge --abort
>>>>>>> root

git rev-list --reverse root..sequence
