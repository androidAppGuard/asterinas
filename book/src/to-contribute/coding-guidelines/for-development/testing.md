# Testing

### Add regression tests for every bug fix (`add-regression-tests`) {#add-regression-tests}

When a bug is fixed,
a test that would have caught the bug should accompany the fix.
Include a reference to the issue number
in a comment so future readers
can recover the original context.

#### Steps

1. Decide whether the change fixes a bug, including regressions found during review.
2. Identify the smallest observable scenario that would have failed before the fix.
3. Require a regression test in the appropriate test suite, with an issue or PR reference when the historical context matters.
4. If a test is impossible or too expensive, require the PR to explain the constraint and add the closest practical coverage.

See also:
PR [#2962](https://github.com/asterinas/asterinas/pull/2962).

### Test user-visible behavior, not internals (`test-visible-behavior`) {#test-visible-behavior}

Tests should validate observable, user-facing outcomes.
Prefer testing through public APIs
rather than exposing internal constants in test code.

Name tests after the behavior or specification concept being verified,
not after internal implementation details.
Using kernel-internal names in user-space regression tests
creates unnecessary coupling.

#### Steps

1. Read each new test name, setup, and assertion to identify the behavior being specified.
2. Check that the test reaches the code through a public API, syscall, documented interface, or stable component boundary.
3. Reject tests that expose private constants, internal state, or implementation-only names solely to make the assertion possible.
4. Ask for the test name and assertions to describe the user-visible behavior or specification rule being verified.

See also:
PR [#2926](https://github.com/asterinas/asterinas/pull/2926).

### Use assertion macros, not manual inspection (`use-assertions`) {#use-assertions}

Use language- or framework-provided assertion helpers
instead of printing values and manually inspecting output.
Assertions provide clear failure messages
and make tests self-checking.

#### Steps

1. Search test changes for `printf`, `println`, logs, comments, or manual output that stands in for verification.
2. Require assertions for expected values, errors, side effects, exit statuses, and state transitions.
3. Prefer assertion helpers that print both expected and actual values when they fail.
4. Keep diagnostic output only as additional context after the test already has self-checking assertions.

See also:
PR [#2877](https://github.com/asterinas/asterinas/pull/2877)
and [#2926](https://github.com/asterinas/asterinas/pull/2926).

### Clean up resources after every test (`test-cleanup`) {#test-cleanup}

Always clean up resources after a test:
close file descriptors, unlink temporary files,
and call `waitpid` on child processes.
Leftover resources can cause flaky failures
in subsequent tests.

```c
// Good — cleanup after use
int fd = open("/tmp/test_file", O_CREAT | O_RDWR, 0644);
// ... test logic ...
close(fd);
unlink("/tmp/test_file");
```

#### Steps

1. List resources the test creates or acquires: files, fds, sockets, mounts, children, threads, and global settings.
2. Check normal, failure, timeout, and early-return paths for cleanup.
3. Require unique temporary names or isolated directories when tests can run repeatedly or in parallel.
4. Verify that child processes are waited for and persistent kernel or filesystem state is restored before the test exits.

See also:
PR [#2926](https://github.com/asterinas/asterinas/pull/2926)
and [#2969](https://github.com/asterinas/asterinas/pull/2969).
