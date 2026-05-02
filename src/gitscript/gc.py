def maybe_gc(commit):
    stack = [commit]

    while stack:
        c = stack.pop()
        if c.refcount > 0:
            continue

        parent = c.parent
        if parent:
            parent.refcount -= 1
            if parent.refcount == 0:
                stack.append(parent)

        # delete c (Python GC handles memory)