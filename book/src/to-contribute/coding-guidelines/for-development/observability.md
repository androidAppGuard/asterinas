# Observability

### Use OSTD logging macros exclusively (`ostd-log-only`) {#ostd-log-only}

All OSTD-based crates must use the logging macros
provided by the [`ostd::log`] module:
`debug!`, `info!`, `notice!`, `warn!`, `error!`,
`crit!`, `alert!`, `emerg!`.
Import them via `use ostd::prelude::*`
or `use ostd::log::{info, warn, ...}`.

Do not use the third-party [`log`](https://docs.rs/log) crate directly.
OSTD provides a bridge that forwards messages
from third-party crates (e.g., `smoltcp`) that use `log`,
but first-party code must use OSTD's macros.

Custom output functions, `println!`,
and hand-rolled serial print macros
are not acceptable in production code.
Exception: code that runs before the logging subsystem
is initialized may use early-boot output helpers.

```rust
// Good
info!("VirtIO block device initialized: {} sectors", num_sectors);

// Bad — using the log crate directly
log::info!("VirtIO block device initialized: {} sectors", num_sectors);

// Bad — using println
println!("VirtIO block device initialized: {} sectors", num_sectors);
```

#### Steps

1. Search changed OSTD-based crates for `log::`, `println!`, custom print macros, serial writes used as logs, and ad hoc debug output.
2. Require first-party production logs to use macros from the prelude or `ostd::log`.
3. Check whether any exception is truly early-boot code that runs before logging initialization.
4. Reject manual textual prefixes when the crate or module should use `__log_prefix` instead.

[`ostd::log`]: https://asterinas.github.io/ostd/ostd/log/

### Choose appropriate log levels (`log-levels`) {#log-levels}

OSTD provides eight log levels matching the severity levels
described in [`syslog(2)`]:

| Level | Use for |
|-------|---------|
| `emerg!` | System is unusable; immediately before `abort()`. |
| `alert!` | Action must be taken immediately. |
| `crit!` | Critical conditions: unrecoverable resource exhaustion. |
| `error!` | Serious but recoverable failures: invariant violations, I/O errors. |
| `warn!` | Recoverable problems: fallback paths taken, deprecated usage detected. |
| `notice!` | Normal but significant events: CPU online, security feature activated. |
| `info!` | Routine informational events: subsystem initialization, configuration changes. |
| `debug!` | Development diagnostics: state transitions, intermediate values, per-packet tracing. |

Use `error!` for failures that the system can recover from.
Use `crit!` or `emerg!` only for failures immediately before a halt or abort.
A log statement that fires on every syscall
or every timer tick must use `debug!`.

#### Steps

1. Review each added or changed log statement and identify the condition that emits it and how often it can occur.
2. Match the condition to the severity table rather than to the author's desire for visibility.
3. Require routine, high-frequency, or diagnostic logs to use `debug!`.
4. Require `crit!`, `alert!`, or `emerg!` only when the surrounding control flow is handling an unrecoverable or immediately actionable condition.

[`syslog(2)`]: https://man7.org/linux/man-pages/man2/syslog.2.html

### Define a log prefix for each crate (`log-prefix`) {#log-prefix}

Every OSTD-based crate must define a `__log_prefix` macro at its crate root (in `lib.rs`),
before any `mod` declarations.
This labels all log messages from the crate:

```rust
// Set this crate's log prefix for `ostd::log`.
macro_rules! __log_prefix {
    () => {
        "virtio: "
    };
}
```

Convention: use the lowercase crate name (without `aster_` prefix), followed by `: `.
For example: `"virtio: "`, `"pci: "`, `"uart: "`.

Subsystem modules within a crate can override the prefix
by defining their own `__log_prefix` at the top of `mod.rs`:

```rust
// Set this module's log prefix for `ostd::log`.
macro_rules! __log_prefix {
    () => {
        "net: "
    };
}
```

Child modules inherit the override automatically.

Do not put `#[rustfmt::skip]` or any other attribute on `__log_prefix` definitions —
it causes a compiler ambiguity error (E0659).

Do not use manual bracket prefixes like `[IOMMU]` or `[Virtio]:`.
The `__log_prefix` mechanism replaces them.

#### Steps

1. For each changed OSTD-based crate or module that emits logs, open its crate root or `mod.rs`.
2. Check that `__log_prefix` appears before any `mod` declaration and has no attributes.
3. Verify that the prefix is lowercase, stable, and follows the crate or subsystem naming convention with a trailing `: `.
4. Flag manual prefixes in individual log messages once the macro supplies the source label.
