git config alias.emit -c source -c root_ref -p out '!
    git branch emit_cursor $source
    git merge -s is emit_loop
    <<<<<<< emit_cursor
        git merge --abort emit_loop
    =======
        git checkout $out
        git cherry-pick emit_cursor
        git checkout emit_cursor
        git reset HEAD~1
        git merge --continue emit_loop
    >>>>>>> $root_ref
'

git config alias.emit-triple -p out -c quote_ref '!
    git checkout $out
    git cherry-pick $quote_ref
    git cherry-pick $quote_ref
    git cherry-pick $quote_ref
'

git tag root
git branch template root
git checkout template
git commit -m="""git config alias.emit -c source -c root_ref -p out '!
    git branch emit_cursor $source
    git merge -s is emit_loop
    <<<<<<< emit_cursor
        git merge --abort emit_loop
    =======
        git checkout $out
        git cherry-pick emit_cursor
        git checkout emit_cursor
        git reset HEAD~1
        git merge --continue emit_loop
    >>>>>>> $root_ref
'

git config alias.emit-triple -p out -c quote_ref '!
    git checkout $out
    git cherry-pick $quote_ref
    git cherry-pick $quote_ref
    git cherry-pick $quote_ref
'

git tag root
git branch template root
git checkout template
git commit -m=@

git branch output root
git branch cursor template
git branch quote root
git checkout quote
git commit 34
git branch marker root
git checkout marker
git commit 64

git merge -s is loop
<<<<<<< cursor
    git merge --abort loop
=======
    git merge -s eq marker_check
    <<<<<<< cursor
        git emit-triple output quote
        git emit template root output
        git emit-triple output quote
    =======
        git checkout output
        git cherry-pick cursor
    >>>>>>> marker

    git checkout cursor
    git reset HEAD~1
    git merge --continue loop
>>>>>>> root

git log --reverse root..output
"""

git branch output root
git branch cursor template
git branch quote root
git checkout quote
git commit 34
git branch marker root
git checkout marker
git commit 64

git merge -s is loop
<<<<<<< cursor
    git merge --abort loop
=======
    git merge -s eq marker_check
    <<<<<<< cursor
        git emit-triple output quote
        git emit template root output
        git emit-triple output quote
    =======
        git checkout output
        git cherry-pick cursor
    >>>>>>> marker

    git checkout cursor
    git reset HEAD~1
    git merge --continue loop
>>>>>>> root

git log --reverse root..output

