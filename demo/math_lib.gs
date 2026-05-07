git config alias.inc 'commit 1'
git config alias.add_one -p target '!
    git branch one main
    git checkout one
    git commit 1
    git checkout target
    git cherry-pick one -s=add
'

git push inc add_one
