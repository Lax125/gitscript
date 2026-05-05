git tag root

# Read the inclusive upper bound.
git checkout -b prompt root
git commit -m "Max number: "
git checkout -b max_value root

git merge -s is read_number
<<<<<<< max_value
    git log --oneline root..prompt
    git commit || git merge --continue read_number
    git merge --abort read_number
=======
    git merge --abort read_number
>>>>>>> root

# Start testing candidates at 2.
git checkout -b one root
git commit 1
git checkout -b two root
git commit 2

git branch primes root
git branch candidate two
git branch walker root
git branch remainder root
git branch composite root

# For each candidate, try dividing by every prime found so far.
git merge -s lte
<<<<<<< candidate
    git checkout composite
    git reset root
    git checkout walker
    git reset primes

    # Walk known primes. A zero remainder marks the candidate composite and
    # aborts this inner loop early.
    git merge -s is walk_primes
    <<<<<<< walker
        git merge --abort
    =======
        git checkout remainder
        git reset candidate
        git cherry-pick walker -s=mod

        git merge -s eq
        <<<<<<< remainder
            git checkout composite
            git reset root
            git commit 1
            git merge --abort walk_primes
        =======
            git checkout walker
            git reset HEAD~1
        >>>>>>> root

        git merge --continue
    >>>>>>> root

    # Prime candidates are appended to the output list.
    git merge -s eq
    <<<<<<< composite
        git checkout primes
        git cherry-pick candidate
    =======
        git merge --abort
    >>>>>>> root

    git checkout candidate
    git cherry-pick one -s=add
    git merge --continue
=======
    git merge --abort
>>>>>>> max_value

# Print the primes in ascending order.
git rev-list --reverse root..primes
