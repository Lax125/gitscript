git tag root

# Read the starting value.
git checkout -b n
git commit  # initial number

# Constants used for parity and for the odd step.
git checkout -b one root
git commit -m 1
git checkout -b two root
git commit -m 2
git checkout -b three root
git commit -m 3

git branch sequence root
git branch parity root

# Keep appending n, then transform it until it reaches one.
git merge -s >
<<<<<<< n
    git checkout sequence
    git cherry-pick n

    git checkout parity
    git reset n
    git cherry-pick two -s=%

    git merge -s ==
    <<<<<<< parity
        # even: n = n / 2
        git checkout n
        git cherry-pick two -s=/
    =======
        # odd: n = 3n + 1
        git checkout n
        git cherry-pick three -s=*
        git cherry-pick one -s=+
    >>>>>>> root

    git merge --continue
=======
    git merge --abort
>>>>>>> one

# Include the terminal one and print the full sequence.
git checkout sequence
git cherry-pick n
git rev-list --reverse root..sequence
