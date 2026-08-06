# Efficiency

### Avoid O(n) algorithms on hot paths (`no-linear-hot-paths`) {#no-linear-hot-paths}

System call dispatch, scheduler enqueue,
and frequent query operations
must not introduce O(n) complexity
where n is a quantity that can be large
(number of processes, number of file descriptors, etc.).
Demand sub-linear alternatives.

```rust
// Bad — O(n) scan on every enqueue
fn select_cpu(&self, cpus: &[CpuState]) -> CpuId {
    cpus.iter()
        .min_by_key(|c| c.load())
        .expect("at least one CPU")
        .id()
}

// Good — maintain a priority queue
// so selection is O(log n)
fn select_cpu(&self) -> CpuId {
    self.cpu_heap.peek().expect("at least one CPU").id()
}
```

#### Steps

1. Identify changed code on frequent paths: syscalls, scheduling, page faults, networking, descriptor lookup, or interrupt-adjacent work.
2. For each loop, scan, sort, allocation, or traversal there, name `n` and whether it can be large.
3. Require an indexed, cached, queued, tree-based, or otherwise sub-linear design when the operation repeats on a hot path over large `n`.
4. Accept a linear operation only when the bound is small and explicit, or when measured evidence shows it is not on a hot path.

See also:
PR [#1790](https://github.com/asterinas/asterinas/pull/1790).

### Minimize unnecessary copies and allocations (`minimize-copies`) {#minimize-copies}

Extra data copies —
serializing to a stack buffer before writing,
cloning an `Arc` when a `&` reference suffices,
collecting into a `Vec` when an iterator would do —
should be avoided.

```rust
// Bad — unnecessary Arc::clone
fn process(&self, stream: Arc<DmaStream>) {
    let s = stream.clone();
    s.sync();
}

// Good — borrow when ownership is not needed
fn process(&self, stream: &DmaStream) {
    stream.sync();
}
```

#### Steps

1. Search the diff for `clone`, `to_vec`, `collect`, temporary buffers, serialization steps, and ownership changes from references to owned values.
2. Decide whether the new owner is needed for lifetime, mutation, sharing across tasks, or storage beyond the call.
3. Require borrowing, slicing, iterator chaining, or moving an existing value when ownership or allocation is not necessary.
4. Keep copies that cross protection, DMA, userspace, or lifetime boundaries only when the boundary makes the copy part of the correctness contract.

See also:
PR [#2582](https://github.com/asterinas/asterinas/pull/2582)
and [#2725](https://github.com/asterinas/asterinas/pull/2725).

### No premature optimization without evidence (`no-premature-optimization`) {#no-premature-optimization}

Performance optimizations
must be justified with data.
Introducing complexity
to solve a non-existent problem is rejected.
If you claim a change improves performance,
show the numbers.

#### Steps

1. Identify changes whose main justification is speed, memory use, cache behavior, or reduced instruction count.
2. Ask for benchmark data, profiling output, or a concrete complexity argument that matches the affected workload.
3. Compare the performance gain against added branches, unsafe code, synchronization complexity, API complexity, and maintenance cost.
4. Prefer the simpler implementation when the optimization lacks evidence or targets an unimportant path.
