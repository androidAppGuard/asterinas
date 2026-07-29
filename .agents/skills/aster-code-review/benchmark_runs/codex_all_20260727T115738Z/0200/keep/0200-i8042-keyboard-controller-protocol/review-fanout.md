---
date: 2026-07-27
mode: diff
base: a3c5ab8cb
head: 2c4da30fe
branch: HEAD
---

# Summary

This change cleanly introduces a dedicated keyboard component and wires framebuffer keyboard input into the console stack, but the review found several issues that should be addressed before merge.

The highest-risk correctness problems are in the new i8042 path: initialization still panics on legitimate allocation failures, `Status::has_error()` misses standalone timeout/parity bits, and `parse_inputkey()` reads the data port before proving the output buffer is full. Keyboard translation also mishandles Caps Lock and dual Shift state, which will produce visibly wrong input.

The callback paths need restructuring. Both the keyboard callback registry and framebuffer console callback registry invoke callbacks while holding spinlocks; the current TTY callback can allocate, lock line-discipline state, and echo back to framebuffer output. Use an RCU/snapshot style so locks are dropped before callbacks run.

Maintainability findings are mostly about making the new component easier to review and extend: name the i8042 constants, avoid coupling generic keyboard events to xterm encoding, qualify cross-module statics, and fill in crate-level docs. No security-specific findings survived the security pass.

## Maintainability

### `kernel/comps/keyboard/src/i8042_chip/controller.rs` line 29

> ```diff
> 28:     // Disable devices so that they won't send data at the wrong time and mess up initialisation.
> 29:     status_or_command_port.write(0xAD);
> 30:     status_or_command_port.write(0xA7);
> ```

`no-magic-number` (major): The i8042 setup path writes raw protocol bytes such as `0xAD`, `0xA7`, `0x20`, `0x60`, `0xAA`, and checks `0x55` inline. These are external controller commands and response values, so their meaning is not local to the arithmetic and readers have to re-derive the protocol from the spec while reviewing initialization.

**Fix.** Introduce named constants or small helper methods for the controller commands and response values, for example `DISABLE_FIRST_PORT`, `DISABLE_SECOND_PORT`, `READ_CONFIGURATION`, `WRITE_CONFIGURATION`, `SELF_TEST`, and `SELF_TEST_PASSED`, then write those names at the call sites.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 15

> ```diff
> 15: use super::controller::{Status, DATA_PORT, STATUS_OR_COMMAND_PORT};
> ```

`qualified-fn-imports` (minor): `DATA_PORT` and `STATUS_OR_COMMAND_PORT` are statics imported directly from `controller`, so later reads like `DATA_PORT.get()` look local rather than module-owned.

**Fix.** Import the parent module and qualify the statics at use sites, e.g. `use super::controller::{self, Status};` and then `controller::DATA_PORT.get()` / `controller::STATUS_OR_COMMAND_PORT.is_completed()`.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 16

> ```diff
> 16: use crate::{InputKey, KEYBOARD_CALLBACKS};
> ```

`qualified-fn-imports` (minor): `KEYBOARD_CALLBACKS` is a crate-root static imported directly, which hides that the interrupt handler is reaching back into the crate-level callback registry.

**Fix.** Remove `KEYBOARD_CALLBACKS` from the import and call it as `crate::KEYBOARD_CALLBACKS` at the lock site.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 35

> ```diff
> 35:     let Ok(mappped_irq_line) = IRQ_CHIP.get().unwrap().map_isa_pin_to(irq_line, 1) else {
> ```

`no-magic-number` (minor): `map_isa_pin_to(irq_line, 1)` uses the raw ISA pin number for the keyboard IRQ. The value `1` is an external hardware assignment, so its meaning is not clear at the call site.

**Fix.** Introduce a named constant such as `const KEYBOARD_IRQ_PIN: u8 = 1;` and pass `KEYBOARD_IRQ_PIN` to `map_isa_pin_to`.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 58

> ```diff
> 58: #[derive(Debug, Clone, Copy)]
> ```

`alphabetical-attrs` (nit): The `ScanCode` derive list is not alphabetically sorted: `Debug` appears before `Clone` and `Copy`.

**Fix.** Sort the derive traits alphabetically: `#[derive(Clone, Copy, Debug)]`.

### `kernel/comps/keyboard/src/lib.rs` line 3

> ```diff
> 3: //! Handle keyboard input.
> ```

`module-docs` (minor): The new `aster-keyboard` crate is a major component, but its module docs only say `Handle keyboard input.` and do not describe the key public types, callback API, or how the generic keyboard layer relates to the `i8042_chip` backend.

**Fix.** Expand the crate-level `//!` docs to cover the module purpose, the roles of `InputKey`, `KeyboardCallback`, and `register_callback`, and the fact that `i8042_chip` is the current architecture-specific backend.

### `kernel/comps/keyboard/src/lib.rs` line 35

> ```diff
> 35: #[derive(Clone, Copy, Debug, PartialEq, Eq)]
> ```

`alphabetical-attrs` (nit): The `InputKey` derive list is not alphabetically sorted: `PartialEq` appears before `Eq`.

**Fix.** Sort the derive traits alphabetically: `#[derive(Clone, Copy, Debug, Eq, PartialEq)]`.

### `kernel/comps/keyboard/src/lib.rs` line 195

> ```diff
> 191: impl InputKey {
> 192:     /// Get the xterm control sequences for this key.
> 193:     ///
> 194:     /// Reference: <https://www.x.org/docs/xterm/ctlseqs.pdf>
> 195:     pub fn as_xterm_control_sequences(&self) -> &[u8] {
> ```

`coupling-cohesion` (major): `InputKey::as_xterm_control_sequences` makes the keyboard component own xterm terminal encoding details. That couples a generic keyboard input model to one console protocol, so non-console keyboard consumers must depend on terminal semantics and future terminal changes require editing the keyboard crate.

**Fix.** Keep `InputKey` as the keyboard-level event type and move xterm byte translation into the framebuffer console or a dedicated console adapter, e.g. `FramebufferConsole` can convert `InputKey` to `VmReader` before invoking `ConsoleCallback`.

## Correctness

### `kernel/comps/framebuffer/src/console.rs` line 230

> ```diff
> let buffer = key.as_xterm_control_sequences();
> for callback in console.callbacks.lock().iter() {
>     let reader = VmReader::from(buffer);
>     callback(reader);
> }
> ```

`no-io-under-spinlock` (major): `console.callbacks.lock()` is held while invoking console callbacks. The current TTY callback allocates a `Vec`, pushes into the line discipline, and can echo through `ConsoleDriver::echo_callback()` back into `FramebufferConsole::send()`, so keyboard input can perform framebuffer I/O while this spinlock is held.

**Fix.** Shared with the other callback-lock comment: do not call callbacks under callback-list spinlocks. Store callback lists behind `Rcu` like the virtio console, or otherwise copy/snapshot the callback pointers, drop the lock, and then invoke them.

### `kernel/comps/keyboard/src/i8042_chip/controller.rs` line 25

> ```diff
> let data_port = IoPort::acquire(0x60).unwrap();
> let status_or_command_port = IoPort::acquire(0x64).unwrap();
> ```

`propagate-errors` (major): `IoPort::acquire(0x60).unwrap()` and the following `IoPort::acquire(0x64).unwrap()` can panic during component initialization if either PIO port is already allocated or denied, even though `init()` returns `Result<(), ComponentInitError>` and can report initialization failure.

**Fix.** Map both `IoPort::acquire` errors into `ComponentInitError::UninitializedDependencies` or another appropriate init error and return them with `?` instead of panicking.

### `kernel/comps/keyboard/src/i8042_chip/controller.rs` line 154

> ```diff
> pub(super) fn has_error(&self) -> bool {
>     self.contains(Self::SYSTEM_FLAG | Self::TIME_OUT_ERROR | Self::PARITY_ERROR)
> }
> ```

Incorrect status predicate (major): `Status::has_error()` uses `contains(Self::SYSTEM_FLAG | Self::TIME_OUT_ERROR | Self::PARITY_ERROR)`, which only returns `true` when all three bits are set. A normal `TIME_OUT_ERROR` or `PARITY_ERROR` alone is therefore treated as valid input and the driver can deliver a corrupted scancode.

**Fix.** Check only the actual error bits with an any-bit predicate, e.g. `self.intersects(Self::TIME_OUT_ERROR | Self::PARITY_ERROR)`. Do not include `SYSTEM_FLAG` as an error bit.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 33

> ```diff
> let mut irq_line = IrqLine::alloc().unwrap();
> ```

`propagate-errors` (major): `IrqLine::alloc().unwrap()` can panic when IRQ lines are exhausted (`IrqLine::alloc()` returns `Error::NotEnoughResources`), aborting component initialization instead of returning the existing `ComponentInitError` path.

**Fix.** Propagate the allocation failure through `init()` by mapping it into `ComponentInitError`, matching the existing error handling for `map_isa_pin_to`.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 50

> ```diff
> for callback in KEYBOARD_CALLBACKS.lock().iter() {
>     callback(key);
> }
> ```

`no-io-under-spinlock` (major): `KEYBOARD_CALLBACKS.lock()` is held while each callback runs. The registered framebuffer callback can enter TTY input handling and echo back to the framebuffer, so IRQ delivery performs substantial lock-taking and framebuffer I/O while holding the keyboard callback-list spinlock.

**Fix.** Shared with the other callback-lock comment: use a callback storage pattern that lets the IRQ path take a stable snapshot and drop the lock before invoking callbacks, such as the `Rcu<Box<Vec<_>>>` pattern used by the virtio console.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 310

> ```diff
> let status = Status::read();
> let code = ScanCode::read();
> 
> if status.has_error() || code.has_error() {
>     ...
> }
> 
> if !status.has_data_to_read() {
> ```

Invalid device read (major): `parse_inputkey()` reads port `0x60` before checking `status.has_data_to_read()`. On a spurious IRQ1, or any interrupt where `OUTPUT_BUFFER_IS_FULL` is clear, this reads the data port despite the controller contract saying that bit must be set first.

**Fix.** Check `status.has_data_to_read()` before calling `ScanCode::read()`, and return `InputKey::Ign` without touching `DATA_PORT` when the output buffer is empty.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 313

> ```diff
> log::warn!(
>     "i8042 keyboard error detected, code:{:?} status:{:?}",
>     code,
>     status
> );
> ...
> log::warn!("i8042 keyboard has no data to read");
> ```

`ostd-log-only` (minor): The new OSTD-based `aster-keyboard` crate logs through `log::warn!` directly. First-party OSTD crates should use `ostd::log` macros so log routing and prefixes work consistently.

**Fix.** Import the OSTD logging macro, for example `use ostd::log::warn;`, then call `warn!(...)` at both warning sites and remove the direct `log` dependency if it is no longer needed.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 348

> ```diff
> if code.is_shift() {
>     if code.is_pressed() {
>         SHIFT_KEY.store(true, Ordering::Relaxed);
>     } else {
>         SHIFT_KEY.store(false, Ordering::Relaxed);
>     }
>     return InputKey::Ign;
> }
> ```

Incorrect modifier state (minor): `SHIFT_KEY` is a single boolean for both shift keys. Pressing left shift, pressing right shift, then releasing left shift stores `false`, so the next key is treated as unshifted even though right shift is still held.

**Fix.** Track left and right shift independently, or maintain a pressed-shift count, and consider shift active while at least one shift key remains pressed.

### `kernel/comps/keyboard/src/i8042_chip/keyboard.rs` line 368

> ```diff
> if ctrl_key {
>     code.ctrl_map()
> } else if shift_key || caps_lock {
>     code.shift_map()
> } else {
>     code.plain_map()
> }
> ```

Incorrect modifier logic (major): `shift_key || caps_lock` applies the shifted map to every key whenever Caps Lock is on. With Caps Lock enabled, pressing `1` produces `!`, and pressing `Shift+A` still produces uppercase `A` instead of lowercase `a`.

**Fix.** Apply Caps Lock only to alphabetic keys, and use XOR semantics between Shift and Caps Lock for letters while leaving digits and punctuation controlled only by Shift.

### `kernel/comps/keyboard/src/lib.rs` line 14

> ```diff
> use ostd::sync::{LocalIrqDisabled, SpinLock};
> 
> #[cfg(target_arch = "x86_64")]
> mod i8042_chip;
> ```

`log-prefix` (minor): The new OSTD-based crate has no crate-root `__log_prefix` before its first `mod` declaration, so its OSTD log messages will not get the required crate prefix once the logging macros are corrected.

**Fix.** Add a crate-root prefix before `mod i8042_chip`, for example:

```rust
macro_rules! __log_prefix {
    () => {
        "keyboard: "
    };
}
```
