# Correctness

### Use checked or saturating arithmetic (`checked-arithmetic`) {#checked-arithmetic}

Use checked or saturating arithmetic
for operations that could overflow.
Prefer explicit overflow handling
over silent wrapping:

```rust
// Good — overflow is handled explicitly
let total = base.checked_add(offset)
    .ok_or(Error::new(Errno::EOVERFLOW))?;

// Good — clamps instead of wrapping
let remaining = budget.saturating_sub(cost);

// Bad — may silently wrap in release builds
let total = base + offset;
```

If wraparound behavior is intentional,
use explicit `wrapping_*` or `overflowing_*` operations
and document why wrapping is correct.

#### Steps

1. Identify arithmetic on addresses, offsets, lengths, counts, indexes, capacities, time values, and externally supplied integers.
2. Decide whether any operand can exceed the safe range in release builds.
3. Require `checked_*`, `saturating_*`, typed range validation, or explicit error handling when overflow is possible.
4. Accept `wrapping_*` or `overflowing_*` only when wraparound is part of the contract and the code documents why it is correct.

### Use `debug_assert` for correctness-only checks (`debug-assert`) {#debug-assert}

Assertions verifying invariants
that should never fail in correct code
belong in `debug_assert!`, not `assert!`.
`debug_assert!` is compiled out in release builds,
so the check catches bugs during development
without costing anything in production.

```rust
debug_assert!(self.align.is_multiple_of(PAGE_SIZE));
debug_assert!(self.align.is_power_of_two());
```

#### Steps

1. Find newly added `assert!`, `debug_assert!`, and equivalent invariant checks.
2. Classify each check as recoverable condition, boundary validation, or internal invariant.
3. Require normal error handling for recoverable conditions and boundary validation for untrusted input.
4. Prefer `debug_assert!` for internal correctness-only invariants unless the check must remain in release builds to preserve soundness or security.

See also:
[std::debug_assert!](https://doc.rust-lang.org/std/macro.debug_assert.html)
and [Rust Reference: `debug_assertions`](https://doc.rust-lang.org/reference/conditional-compilation.html#debug_assertions).

### Propagate errors with `?` (`propagate-errors`) {#propagate-errors}

Use the `?` operator
to propagate errors idiomatically.
In kernel code,
`.unwrap()` is rejected
wherever failure is a legitimate possibility.

```rust
// Good — propagate with ?
let tsc_info = cpuid.get_tsc_info()?;
let frequency = tsc_info.nominal_frequency()?;

// Bad — unwrap hides the failure path
let tsc_info = cpuid.get_tsc_info().unwrap();
```

#### Steps

1. Search the changed code for `.unwrap()`, `.expect()`, unchecked indexing, and conversions that can panic.
2. For each panic path, determine whether failure is impossible by construction, a kernel bug, or a legitimate runtime outcome.
3. Require `?`, `ok_or`, `map_err`, or explicit recovery when failure can come from userspace, hardware, allocation, I/O, or normal kernel state.
4. Allow a panic only when the invariant is local and undeniable; otherwise ask for a precise error path or a documented invariant.

See also:
_The Rust Programming Language_, Chapter 9 "Error Handling"
and [Rust by Example: unpacking options and defaults with `?`](https://doc.rust-lang.org/rust-by-example/std/result/question_mark.html).
