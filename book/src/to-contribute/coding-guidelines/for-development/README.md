# For Development

*Does the code do the right thing — including on error, concurrent, and hot paths — and is it proven by tests?*

This is the index of the **development** guidelines.
Each subsection is its own page,
and each entry below links a stable `short-name` to its guideline,
with a one-line gist so a reader (or a review tool) can grasp the guideline before opening it.

## Index

**[Correctness](correctness.md)**
- [`checked-arithmetic`](correctness.md#checked-arithmetic): Handle possible overflow with checked or saturating arithmetic; apply when arithmetic may overflow and wraparound is not intended.
- [`debug-assert`](correctness.md#debug-assert): Use `debug_assert!` for invariants that should never fail in correct code; apply when a check catches internal logic bugs and release code must not rely on it.
- [`propagate-errors`](correctness.md#propagate-errors): Propagate legitimately recoverable failures with `?` instead of `.unwrap()`; apply when an operation can normally return an error.

**[Concurrency](concurrency.md)**
- [`lock-ordering`](concurrency.md#lock-ordering): Establish and document one hierarchical lock order; apply when code can acquire multiple locks or adds a new lock path.
- [`no-io-under-spinlock`](concurrency.md#no-io-under-spinlock): Release a spinlock before I/O or blocking work; apply whenever such work would run while holding a spinlock.
- [`careful-atomics`](concurrency.md#careful-atomics): Protect correlated fields with one lock and reserve atomics for independent values; apply when choosing synchronization for shared state.
- [`atomic-critical-sections`](concurrency.md#atomic-critical-sections): Keep a check and its conditional action under one lock acquisition; apply whenever state can change between those two operations.

**[Resource Management](resource-management.md)**
- [`raii`](resource-management.md#raii): Acquire resources through guards that release them via `Drop`; apply whenever a resource needs cleanup such as IRQ state, handles, DMA buffers, or locks.

**[Efficiency](efficiency.md)**
- [`no-linear-hot-paths`](efficiency.md#no-linear-hot-paths): Keep hot paths such as syscall dispatch and scheduler enqueue sub-linear; apply when `n` can grow with system workload.
- [`minimize-copies`](efficiency.md#minimize-copies): Avoid copies and allocations when borrowing or streaming suffices; apply whenever ownership or data movement is being designed or reviewed.
- [`no-premature-optimization`](efficiency.md#no-premature-optimization): Justify performance changes with measurements; apply when an optimization would add complexity or claims a speedup.

**[Observability](observability.md)**
- [`ostd-log-only`](observability.md#ostd-log-only): Use `ostd::log` macros instead of the `log` crate or ad hoc output; apply when writing production logs in OSTD-based crates, except early-boot output before logging initializes.
- [`log-levels`](observability.md#log-levels): Choose the log level that matches event severity and frequency; apply whenever adding or changing a log statement.
- [`log-prefix`](observability.md#log-prefix): Define `__log_prefix` before any `mod` in each OSTD-based crate; apply when adding a crate or overriding a subsystem module's prefix.

**[Testing](testing.md)**
- [`add-regression-tests`](testing.md#add-regression-tests): Add a test that would have caught each bug; apply when fixing a bug and record its issue number.
- [`test-visible-behavior`](testing.md#test-visible-behavior): Test observable behavior through public APIs and name tests after that behavior; apply when writing tests for user-visible or specified behavior.
- [`use-assertions`](testing.md#use-assertions): Use assertion helpers instead of print-and-inspect checks; apply whenever a test must verify a result.
- [`test-cleanup`](testing.md#test-cleanup): Release every resource a test acquires; apply when tests create file descriptors, temporary files, or child processes.

No **path-specific** guidelines yet.
