# GitScript

GitScript is an esoteric programming language where instructions look like git commands and control structures look like
merge conflicts.

## Examples

### Hello World
```
git commit -m "Hello, World!"  # add null-terminated string to history as multiple commits
git log  # display values in history backwards as characters until 0 (null) is reached
```

### Compute GCD via Euclidean Algorithm
```
git checkout -b a
git commit  # parse user input as integer

git checkout -b b
git commit  # parse user input as integer

# branch whose label's value is higher is executed until both are equal
<<<<<<< a
    git checkout a
    git merge b -s=-
=======
    git checkout b
    git merge a -s=-
>>>>>>> b

git show  # print result
```
