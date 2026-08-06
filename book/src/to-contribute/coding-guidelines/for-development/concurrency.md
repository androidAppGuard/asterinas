# Concurrency

### Establish and enforce a consistent lock order (`lock-ordering`) {#lock-ordering}

Acquiring two locks in different orders
from different code paths
is a potential deadlock.
Hierarchical lock order must be established and documented.

```rust
pub(super) fn set_control(
    self: Arc<Self>,
    process: &Process,
) -> Result<()> {
    // Lock order: group of process -> session inner -> job control
    let process_group_mut = process.process_group.lock();
    // ...
}
```

#### Steps

1. List every lock acquired by the changed code, including locks acquired indirectly through helper calls.
2. Check whether any path can hold two or more locks at once; compare the acquisition order with nearby code and existing comments.
3. Require an explicit lock-order comment when the order is non-obvious or spans multiple objects or subsystems.
4. Report any path that can acquire the same lock pair in the opposite order, including error paths and callbacks invoked while locked.

See also:
PR [#2942](https://github.com/asterinas/asterinas/pull/2942).

### Never do I/O or blocking operations while holding a spinlock (`no-io-under-spinlock`) {#no-io-under-spinlock}

Holding a spinlock while performing I/O
or blocking operations is a deadlock hazard.
Use a sleeping mutex or restructure
to drop the lock first.

```rust
// Good — spinlock dropped before I/O
let data = {
    let guard = self.state.lock(); // state: SpinLock<...>
    guard.pending_data.clone()
};
self.device.write(&data)?;

// Bad — I/O while holding spinlock
let guard = self.state.lock(); // state: SpinLock<...>
self.device.write(&guard.pending_data)?;
```

#### Steps

1. Find critical sections protected by spinlocks or IRQ-disabling guards in the changed code.
2. Inspect calls made while the guard is live, including trait methods and logging paths.
3. Flag I/O, sleeping, waiting, scheduling, user-memory access, or blocking allocation under the guard.
4. Require dropping the guard before blocking work, or using a sleeping mutex when the work must stay protected.

See also:
PR [#925](https://github.com/asterinas/asterinas/pull/925).

### Do not use atomics casually (`careful-atomics`) {#careful-atomics}

When multiple atomic fields
must be updated in concert, use a lock.
Only use atomics when a single value
is genuinely independent.

```rust
// Good — a lock protects correlated fields
struct Stats {
    inner: SpinLock<StatsInner>,
}
struct StatsInner {
    total_bytes: u64,
    total_packets: u64,
}

// Bad — two atomics that must be consistent
// but can be observed in an inconsistent state
struct Stats {
    total_bytes: AtomicU64,
    total_packets: AtomicU64,
}
```

#### Steps

1. Identify newly added atomics and changes to existing atomic fields.
2. Determine whether each atomic value is independent or must stay consistent with another field, flag, counter, or state transition.
3. Require a lock or a single combined state representation when multiple values must be observed or updated together.
4. For accepted atomics, check that the ordering is justified by the synchronization contract and is not chosen casually.

### Critical sections must not be split across lock boundaries (`atomic-critical-sections`) {#atomic-critical-sections}

Operations that must be atomic
(check + conditional action)
must happen under the same lock acquisition.
Moving a comparison outside the critical region
is a correctness bug.

```rust
// Good — check and action under the same lock
let mut inner = self.inner.lock();
if inner.state == State::Ready {
    inner.state = State::Running;
    inner.start();
}

// Bad — TOCTOU race: state can change
// between the check and the action
let is_ready = self.inner.lock().state == State::Ready;
if is_ready {
    self.inner.lock().state = State::Running;
    self.inner.lock().start();
}
```

#### Steps

1. Look for check-then-act sequences: lookup then insert, state check then transition, permission check then use, or capacity check then allocation.
2. Verify that the checked state cannot change before the action runs.
3. Require one lock acquisition, transaction, or equivalent synchronization primitive to cover the whole sequence.
4. Pay special attention to helper calls and dropped guards that make the critical section look continuous while actually splitting it.

See also:
PR [#2277](https://github.com/asterinas/asterinas/pull/2277).
