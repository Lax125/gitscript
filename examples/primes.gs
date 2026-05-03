git tag root

git checkout -b max
git commit  # maximum number to test

git checkout -b one root
git commit -m 1
git checkout -b two root
git commit -m 2

git branch primes root
git branch candidate two
git branch walker root
git branch remainder root
git branch composite root

git merge -s <=
<<<<<<< candidate
    git checkout composite
    git reset root
    git checkout walker
    git reset primes

    # Walk known primes. A zero remainder marks the candidate composite and
    # resets walker to root, ending this inner loop early.
    git merge -s is
    <<<<<<< walker
        git merge --abort
    =======
        git checkout remainder
        git reset candidate
        git cherry-pick walker -s=%

        git merge -s ==
        <<<<<<< remainder
            git checkout composite
            git reset root
            git commit -m 1
            git checkout walker
            git reset root
        =======
            git checkout walker
            git reset HEAD~1
        >>>>>>> root

        git merge --continue
    >>>>>>> root

    git merge -s ==
    <<<<<<< composite
        git checkout primes
        git cherry-pick candidate
    =======
        git merge --abort
    >>>>>>> root

    git checkout candidate
    git cherry-pick one -s=+
    git merge --continue
=======
    git merge --abort
>>>>>>> max

git rev-list --reverse root..primes
