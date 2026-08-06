# Crates & Modules

### Use workspace dependencies (`workspace-deps`) {#workspace-deps}

Always declare shared dependencies
in the workspace `[workspace.dependencies]` table
and reference them with `.workspace = true`
in member crates.

```toml
# In the workspace root Cargo.toml
[workspace.dependencies]
ostd = { version = "0.17.0", path = "ostd" }
bitflags = "2.6"

# In a member crate's Cargo.toml
[dependencies]
ostd.workspace = true
bitflags.workspace = true
```

#### Steps

1. Inspect `Cargo.toml` changes in member crates for dependency additions or version changes.
2. Check whether the dependency is or should be shared by multiple workspace members.
3. Require shared dependency versions and features to live in the root `[workspace.dependencies]` table.
4. Require member crates to reference shared dependencies with `.workspace = true` rather than repeating versions.

### Add module-level documentation for major components (`module-docs`) {#module-docs}

A module file that serves as
an important kernel component
(e.g., subsystem entry point, major data structure, driver)
should begin with a `//!` comment explaining:
1. What the module does
2. The key types it exposes
3. How it relates to neighboring modules

```rust
//! Virtual memory area (VMA) management.
//!
//! This module defines [`VmMapping`] and associated types,
//! which represent contiguous regions of a process's virtual address space.
//! VMAs are managed by the [`Vmar`] tree in the parent module.
```

#### Steps

1. Identify new module files and changed module entry points for subsystems, drivers, major data structures, and important components.
2. Check whether the file starts with `//!` documentation when it is a major component.
3. Require the module docs to state the module's purpose, key exposed types, and relationship to neighboring modules.
4. Avoid demanding module docs for tiny private helper modules whose purpose is already obvious from the parent.

### Default to the narrowest visibility (`narrow-visibility`) {#narrow-visibility}

Start private,
then widen to `pub(super)`, `pub(crate)`, or `pub`
only when an actual external consumer requires it.

```rust
// Good — restricted to the parent module
pub(super) static I8042_CONTROLLER:
    Once<SpinLock<I8042Controller, LocalIrqDisabled>> = Once::new();

pub(super) fn init() -> Result<(), I8042ControllerError> {
    // ...
}

// Bad — unnecessarily wide
pub static I8042_CONTROLLER: ...
```

Inside the `aster-kernel` crate, `pub(crate)` and `pub` are equivalent,
as the crate has no downstream consumers.
Prefer the shorter `pub`.

#### Steps

1. Review every new or widened `pub`, `pub(crate)`, `pub(super)`, public field, and re-export.
2. Find the actual current consumers of the item.
3. Require the narrowest visibility that reaches those consumers.
4. In `aster-kernel`, prefer `pub` over `pub(crate)` because they are equivalent there.


See also:
PR [#2951](https://github.com/asterinas/asterinas/pull/2951),
[#2605](https://github.com/asterinas/asterinas/pull/2605#discussion_r2720506912),
and [#3154](https://github.com/asterinas/asterinas/pull/3154#discussion_r3100905375).
### Qualify function calls with the parent module (`qualified-fn-imports`) {#qualified-fn-imports}

When importing a free function or a static/constant
from another module,
import the **parent module** and access the item
through it (`module::function()`, `module::CONSTANT`).
Do not import free functions or statics directly by name.

This convention is recommended by
[*The Rust Programming Language*](https://doc.rust-lang.org/book/ch07-04-bringing-paths-into-scope-with-the-use-keyword.html)
and followed by the Rust compiler codebase.
It serves two purposes:

1. The call site makes it clear
   that an imported item is being used,
   not a local one.
2. The module name provides context
   that complements the item name.

```rust
// Good — module-qualified function call
use ostd::irq;

let guard = irq::disable_local();

// Good — module-qualified static access
use ostd::mm::kspace;

let base = kspace::LINEAR_MAPPING_BASE_VADDR;

// Bad — bare function name; unclear origin at call site
use ostd::irq::disable_local;

let guard = disable_local();

// Bad — bare static name; could be mistaken for a local constant
use ostd::mm::kspace::LINEAR_MAPPING_BASE_VADDR;

let base = LINEAR_MAPPING_BASE_VADDR;
```

This guideline applies to **free functions and statics/constants**.
Types, traits, and enum variants
should still be imported directly by name,
following the standard Rust convention.

#### Steps

1. Inspect new `use` statements that import free functions, statics, or constants from another module.
2. Require importing the parent module and calling the item as `module::item`.
3. Leave direct imports of types, traits, enum variants, and macros alone unless another guideline applies.
4. Check call sites for ambiguity: the module qualifier should add useful context without creating excessive path noise.
