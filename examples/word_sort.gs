git tag root

git checkout -b one root
git commit -m 1

git branch words root
git branch word root
git branch word_count root
git branch fences root
git branch remaining root
git branch remaining_count root
git branch new_remaining root
git branch cursor root
git branch depth root
git branch position root
git branch walker root
git branch current_pos root
git branch best_pos root
git branch have_candidate root
git branch comparison root
git branch index root
git branch left_start root
git branch left_end root
git branch right_start root
git branch right_end root
git branch left_cursor root
git branch right_cursor root
git branch selected_start root
git branch selected_end root

git config alias.bounds -r position -l start_depth -l end_depth '!
    git checkout index
    git reset word_count
    git cherry-pick $position -s=-

    git checkout $start_depth
    git reset fences~index

    git checkout index
    git cherry-pick one -s=-

    git checkout $end_depth
    git reset fences~index
    git cherry-pick one -s=-
'

git config alias.compare_words -r left_pos -r right_pos '!
    git bounds $left_pos left_start left_end
    git bounds $right_pos right_start right_end

    git checkout left_cursor
    git reset left_start
    git checkout right_cursor
    git reset right_start
    git checkout comparison
    git reset root

    git merge -s is compare
    <<<<<<< words~left_cursor
        git checkout comparison
        git reset root
        git commit -m 1
        git merge --abort compare
    =======
        git merge -s is
        <<<<<<< words~right_cursor
            git checkout comparison
            git reset root
            git merge --abort compare
        =======
            git merge -s <
            <<<<<<< words~left_cursor
                git checkout comparison
                git reset root
                git commit -m 1
                git merge --abort compare
            =======
                git merge -s >
                <<<<<<< words~left_cursor
                    git checkout comparison
                    git reset root
                    git merge --abort compare
                =======
                    git checkout left_cursor
                    git cherry-pick one -s=+
                    git checkout right_cursor
                    git cherry-pick one -s=+
                    git merge --continue compare
                >>>>>>> words~right_cursor
            >>>>>>> words~right_cursor
        >>>>>>> words~right_end
    >>>>>>> words~left_end
'

git checkout word
git commit -m "

git merge -s is read
<<<<<<< word
    git merge --abort read
=======
    git checkout words
    git commit -m 0
    git cherry-pick root..word

    git checkout word
    git reset root
    git commit -m "
    git merge --continue read
>>>>>>> root

git checkout cursor
git reset words

git merge -s is build
<<<<<<< cursor
    git checkout fences
    git cherry-pick depth
    git checkout remaining_count
    git reset word_count
    git merge --abort build
=======
    git checkout fences
    git cherry-pick depth
    git checkout remaining
    git cherry-pick position
    git checkout word_count
    git cherry-pick one -s=+

    git merge skip_word
    <<<<<<< cursor
        git checkout cursor
        git reset HEAD~1
        git checkout depth
        git cherry-pick one -s=+
        git checkout position
        git cherry-pick one -s=+
        git merge --abort skip_word
    =======
        git checkout cursor
        git reset HEAD~1
        git checkout depth
        git cherry-pick one -s=+
        git merge --continue skip_word
    >>>>>>> root

    git merge --continue build
>>>>>>> root

git merge -s > sort
<<<<<<< remaining_count
    git checkout walker
    git reset remaining
    git checkout have_candidate
    git reset root
    git checkout best_pos
    git reset root

    git merge -s is scan
    <<<<<<< walker
        git merge --abort scan
    =======
        git checkout current_pos
        git reset walker

        git merge
        <<<<<<< have_candidate
            git checkout best_pos
            git reset current_pos
            git checkout have_candidate
            git reset root
            git commit -m 1
        =======
            git compare_words current_pos best_pos
            git merge -s >
            <<<<<<< comparison
                git checkout best_pos
                git reset current_pos
            =======
                git merge --abort
            >>>>>>> root
        >>>>>>> root

        git checkout walker
        git reset HEAD~1
        git merge --continue scan
    >>>>>>> root

    git bounds best_pos selected_start selected_end
    git log words~selected_end..words~selected_start

    git checkout new_remaining
    git reset root
    git checkout walker
    git reset remaining

    git merge -s is rebuild
    <<<<<<< walker
        git merge --abort rebuild
    =======
        git checkout current_pos
        git reset walker

        git merge
        <<<<<<< current_pos
            git merge --abort
        =======
            git checkout new_remaining
            git cherry-pick current_pos
        >>>>>>> best_pos

        git checkout walker
        git reset HEAD~1
        git merge --continue rebuild
    >>>>>>> root

    git checkout remaining
    git reset new_remaining
    git checkout remaining_count
    git cherry-pick one -s=-
    git merge --continue sort
=======
    git merge --abort sort
>>>>>>> root
