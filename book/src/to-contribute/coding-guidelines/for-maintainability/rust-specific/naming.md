# Naming

### Follow Rust CamelCase and acronym capitalization (`camel-case-acronyms`) {#camel-case-acronyms}

Type names follow Rust's CamelCase convention.
Acronyms are title-cased per the Rust API Guidelines:

```rust
// Good
IoMemoryArea
PciDeviceLocation
Nvme
Tcp

// Bad
IOMemoryArea
PCIDeviceLocation
NVMe
TCP
```

#### Steps

1. Inspect new or renamed Rust type names, trait names, enum variants, and type aliases.
2. Identify acronyms and initialisms inside CamelCase names.
3. Require Rust-style title casing for acronyms, such as `Pci`, `Io`, `Tcp`, and `Nvme`.
4. Leave externally mandated spellings only when the external name is part of the exact public contract.

### End closure variables with `_fn` (`closure-fn-suffix`) {#closure-fn-suffix}

Variables holding closures or function pointers
must signal they are callable by ending with `_fn`.
Treating a closure variable
as if it were a data object misleads readers.

```rust
// Good — clearly a callable
let task_fn = self.func.take().unwrap();
let thread_fn = move || {
    let _ = oops::catch_panics_as_oops(task_fn);
    current_thread!().exit();
};

let expired_fn = move |_guard: TimerGuard| {
    ticks.fetch_add(1, Ordering::Relaxed);
    pollee.notify(IoEvents::IN);
};
```

#### Steps

1. Find variables, fields, and parameters whose values are closures or function pointers.
2. Check whether the name makes callability clear at the use site.
3. Require a `_fn` suffix for stored or passed callable values when the type is not obvious from immediate context.
4. Do not require `_fn` for function items called directly by their declared function name.

See also:
PR [#395](https://github.com/asterinas/asterinas/pull/395#discussion_r1402964415)
and [#783](https://github.com/asterinas/asterinas/pull/783#discussion_r1593335375).
