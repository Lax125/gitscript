git checkout -b hello
git commit -m "Hello, world!"
git log main..hello
git log --graph

git checkout -b goodbye HEAD~5  # checkout new branch at commit 8
git commit -m "Goodbye"
git log main..goodbye
git log --graph --all

git log hello...goodbye
