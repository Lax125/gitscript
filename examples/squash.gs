git config alias.squash -c new_parent !'
    git tag temp
    git reset new_parent
    git cherry-pick temp
'
