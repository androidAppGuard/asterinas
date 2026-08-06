# Resource Management

### Use RAII for all resource acquisition and release (`raii`) {#raii}

Resources — IRQ enable/disable state, port numbers,
file handles, DMA buffers, lock guards —
must use the `Drop` trait for automatic cleanup.
Manual `enable()`/`disable()` call pairs are rejected.

```rust
// Good — RAII guard ensures IRQs are re-enabled
fn disable_local() -> DisabledLocalIrqGuard { ... }

impl Drop for DisabledLocalIrqGuard {
    fn drop(&mut self) {
        enable_local_irqs();
    }
}

// Bad — caller can forget to re-enable
fn disable_local_irqs() { ... }
fn enable_local_irqs() { ... }
```

Prefer lexical lifetimes
so the Rust compiler inserts `drop` automatically,
rather than calling `drop()` manually.
When the default drop order is incorrect,
use explicit `drop()` calls.

#### Steps

1. Identify acquired resources: locks, IRQ state, fds, ports, mappings, DMA buffers, allocations, and callbacks.
2. Check every return, `?`, early-exit, panic-relevant path, and cancellation path to see whether the resource is released exactly once.
3. Require a guard type with `Drop` when acquisition and release must be paired across more than a small local scope.
4. Prefer lexical drop order; accept explicit `drop()` only when the ordering is intentional and visible at the point where it matters.

See also:
PR [#164](https://github.com/asterinas/asterinas/pull/164).
