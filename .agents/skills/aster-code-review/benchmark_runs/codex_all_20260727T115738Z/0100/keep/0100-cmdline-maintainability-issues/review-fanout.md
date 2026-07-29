---
date: 2026-07-27
mode: diff
base: b205cacbf
head: 46bb6b9c5
branch: HEAD
---

# Summary

This series cleanly moves kernel parameters toward a declarative registration model and adds useful typed parsers/tests for common Linux-style values. The main risk is that the new dispatcher groups parameters before deciding what to forward, which changes observable init argument ordering and drops duplicate unknown arguments.

Top issues:

- Major: `dispatch_params()` forwards unknown init arguments from a sorted `BTreeMap`, so pre-`--` arguments are reordered and duplicate unknown entries collapse to the last occurrence.
- Major: grouped `CpuList` ranges implement `N-M:used/group` as a stride, not Linux's documented "used CPUs per group" semantics.
- Major: the logger fallback performs early serial output while holding the console-device spinlock.
- Major: the new kernel-parameter compatibility docs overstate implemented behavior for `console`, `i8042.exist=0`, and recognized-but-unimplemented Linux parameters.

Structurally, the parameter framework would be easier to evolve if shared dependencies stayed in the workspace table and public getters avoided exposing `Vec` representation details.

## Maintainability

### `kernel/comps/cmdline/Cargo.toml` line 13

> ```diff
> [dependencies]
>  component.workspace = true
>  log.workspace = true
>  ostd.workspace = true
>  spin.workspace = true
> +inventory = { git = "https://github.com/asterinas/inventory", rev = "9dce587" }
> ```

`workspace-deps` (major): `inventory` is declared directly in `kernel/comps/cmdline/Cargo.toml`, bypassing the workspace dependency table. That gives this crate its own dependency spelling/version source instead of the single workspace representation used for shared dependencies.

**Fix.** Move `inventory` to the root `[workspace.dependencies]` table, then reference it here as `inventory.workspace = true`.

### `kernel/comps/cmdline/src/lib.rs` line 179

> ```diff
> impl InitprocArgs {
>     /// Gets the argument vector (`argv`) of the init process.
>     pub fn argv(&self) -> &Vec<CString> {
>         &self.argv
>     }
> 
>     /// Gets the environment vector (`envp`) of the init process.
>     pub fn envp(&self) -> &Vec<CString> {
>         &self.envp
>     }
> }
> ```

`information-hiding` (minor): `InitprocArgs::argv` and `InitprocArgs::envp` expose `Vec` in their return types even though callers only need to inspect/copy the entries. This leaks the storage choice into the public API and makes a future representation change noisier.

**Fix.** Return slices from these getters, e.g. `pub fn argv(&self) -> &[CString]` and `pub fn envp(&self) -> &[CString]`; existing callers can still use `.to_vec()` on the slice.

### `kernel/comps/cmdline/src/types.rs` line 8

> ```diff
> //! command lines so users of this framework don't need to rewrite them.
> 
> #![allow(dead_code)]
> 
> extern crate alloc;
> ```

`narrow-lint-suppression` (minor): The module-level `#![allow(dead_code)]` suppresses `dead_code` for the entire `types` module, including any future private helpers added here. That makes unused code harder to notice and is broader than the actual planned-unused items.

**Fix.** Remove the module-level suppression. If a specific item is intentionally unused for a concrete future parameter, put `#[expect(dead_code)]` on that item with a short reason.

### `kernel/comps/cmdline/src/types.rs` line 30

> ```diff
> pub struct CpuListSegment {
>     pub start: u32,
>     pub end: u32,
>     /// Step within range, default 1.
>     pub stride: u32,
>     /// Optional group size (the `/N` part). When present, stride selection is
>     /// applied within each group window.
>     pub group: Option<u32>,
> }
> ```

`getter-encapsulation` (minor): `CpuListSegment` exposes all representation fields as `pub`, including invariant-bearing fields such as `stride` and `group`. Once consumers rely on these fields directly, it becomes harder to rename them or tighten invariants like non-zero stride/group values.

**Fix.** Keep the fields private and expose simple getters such as `start()`, `end()`, `stride()`, and `group()`. If external construction is needed, add a checked constructor instead of exposing the raw fields.

## Correctness

### `kernel/comps/cmdline/src/lib.rs` line 412

> ```diff
> 411:     let mut recognized = Vec::new();
> 412:     for (name, occurrences) in &grouped {
> 413:         if let Some(param) = registry.get(name.as_str()) {
> 414:             recognized.push((*param, occurrences));
> 415:         } else {
> ...
> 421:             } else if let Some((key, Some(value))) = occurrences.last().copied() {
> 424:                 let envp_entry = CString::new(key.to_string() + "=" + value).unwrap();
> 425:                 result.envp.push(envp_entry);
> 426:             } else if let Some((key, None)) = occurrences.last().copied() {
> 429:                 let argv_entry = CString::new(key.to_string()).unwrap();
> 430:                 result.argv.push(argv_entry);
> ```

Incorrect argument forwarding (major): `dispatch_params()` forwards unknown init arguments by iterating `grouped`, a `BTreeMap`, after tokenization. That sorts arguments by key and collapses repeated occurrences to `occurrences.last()`: a command line such as `init=/bin/app zeta alpha zeta -- tail` reaches `init` as `tail alpha zeta` instead of preserving the command-line order and both `zeta` occurrences.

**Fix.** Do not derive forwarded `argv`/`envp` entries from the grouped `BTreeMap`. Record unknown non-module tokens during the original `split_arg()` scan, or make a second ordered pass over the original tokens after building `registry`, so every unknown occurrence is forwarded exactly once in command-line order.

### `kernel/comps/cmdline/src/types.rs` line 167

> ```diff
> 110:             // Grouped selection:
> 111:             // for each group window [start+gb, start+gb+g), emit start+gb+within for within=0,stride,2*stride...
> 112:             let g = s.group.unwrap();
> 113:             let stride = s.stride;
> ...
> 166:         let in_group_offset = offset % g;
> 167:         in_group_offset.is_multiple_of(s.stride)
> ```

Incorrect parser semantics (major): `CpuList` implements grouped ranges as a stride inside each group, but Linux’s documented `100-2000:2/25` syntax means “use `2` CPUs from the beginning of each `25`-CPU group” (`100,101,125,126,...`). This code instead treats `2` as a stride, so `contains(102)` returns `true` and `expand_bounded()` emits `100,102,104,...`.

**Fix.** Model the `:<used>/<group>` form as `used` plus `group`, not `stride` plus `group`. For grouped segments, `contains()` should check `offset % group < used`, and expansion should emit `group_start..group_start + used` clipped by `end`; keep stride behavior only for the non-grouped `:<stride>` form.

### `kernel/comps/cmdline/src/types.rs` line 275

> ```diff
> 268:         let mul: u64 = match suf.map(|c| c.to_ascii_uppercase()) {
> 269:             None => 1,
> 270:             Some('K') => 1024u64,
> 271:             Some('M') => 1024u64.pow(2),
> 272:             Some('G') => 1024u64.pow(3),
> 273:             Some('T') => 1024u64.pow(4),
> 274:             Some('P') => 1024u64.pow(5),
> 275:             _ => return Err(ParamError::InvalidValue),
> ```

Incorrect parser semantics (minor): `MetricU64` is introduced as a Linux-style metric suffix parser, but it rejects the valid Linux `E` suffix. `MetricU64::parse_param("1E")` currently returns `ParamError::InvalidValue` even though Linux metric suffixes include `E = 2^60`.

**Fix.** Add `Some('E') => 1024u64.pow(6)` and keep the existing `checked_mul()` overflow handling, then change the test that currently expects `MetricU64::parse_param("1E")` to fail.

### `kernel/comps/logger/src/console.rs` line 29

> ```diff
> 27:         fn write_str(&mut self, s: &str) -> fmt::Result {
> 28:             if self.0.is_empty() {
> 29:                 ostd::early_print!("{}", s);
> 30:             } else {
> 31:                 for console in self.0.values() {
> 32:                     console.send(s.as_bytes());
> ```

`no-io-under-spinlock` (major): `_print()` calls `ostd::early_print!` while still holding the `aster_console::all_devices_lock()` spinlock. `ostd::early_print!` locks `SERIAL_PORT` and writes to the serial device, so the fallback path now performs device I/O under the console-device spinlock.

**Fix.** Release the `all_devices_lock()` guard before using the early serial fallback. For example, check `devices.is_empty()` outside the formatter path, `drop(devices)`, then call `ostd::early_print!`; keep the existing locked path only for registered console devices.

## Documentation

### `book/src/kernel/linux-compatibility/kernel-parameters.md` line 24

> ```diff
> +This parameter may be specified multiple times.
> +Kernel messages are delivered to each listed console.
> ...
> +            let console_name = CONSOLES
> +                .get()
> +                .and_then(|consoles| consoles.first().map(|s| s.as_str()))
> ```

`linux-compat-docs` (major): The `console` documentation says kernel messages are delivered to each listed console, but `SystemConsole::singleton()` still takes only `CONSOLES.first()`. A user booting with `console=ttyS0 console=hvc0` will not get both consoles despite this page saying they should.

**Fix.** Update the `console` entry to document the current first-console-only behavior, or implement multi-console delivery before claiming that every listed `console` receives messages.

### `book/src/kernel/linux-compatibility/kernel-parameters.md` line 62

> ```diff
> +- `0`, `off`, `no`, `false` - treat the i8042 controller as absent (skip probing)
> ...
> +        if !Self::is_present_acpi() {
> +            if !Self::is_present_cmdline() {
> +                return Err(I8042ControllerError::NotPresent);
> ```

`linux-compat-docs` (major): The `i8042.exist=0` documentation says it treats the controller as absent and skips probing, but the code only consults `I8042_EXIST` when ACPI already says the controller is absent. If ACPI says present, `i8042.exist=0` does not skip probing.

**Fix.** Document `i8042.exist` as a positive override only, and either remove the false-valued examples or state that `0`, `off`, `no`, and `false` merely disable the positive override and do not force an ACPI-present controller absent.

### `kernel/comps/cmdline/src/lib.rs` line 473

> ```diff
> +define_unimplemented_param!(
> +    "tsc",
> +    "no_timer_check",
> +    "reboot",
> +    "pci",
> +    "debug",
> +    "panic",
> +    "nr_cpus",
> +    "selinux",
> +    "initrd"
> +);
> ```

`linux-compat-docs` (major): This change registers Linux kernel parameters such as `tsc`, `no_timer_check`, `reboot`, `pci`, `debug`, `panic`, `nr_cpus`, `selinux`, and `initrd` as recognized and consumed, but `book/src/kernel/linux-compatibility/kernel-parameters.md` does not document that user-visible behavior. Users cannot tell these names are swallowed with a warning instead of being forwarded to `init`.

**Fix.** Add these recognized-but-unimplemented parameters to the Kernel Parameters compatibility page, preferably in an `Recognized but unsupported` table that states they are consumed and warn without implementing Linux behavior.
