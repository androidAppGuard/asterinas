# Types & Traits

### Use types to enforce invariants (`rust-type-invariants`) {#rust-type-invariants}

Leverage the type system
to make illegal states _unrepresentable_.

Define newtypes to encode domain constraints.

```rust
// Good — a `Nice` value is guaranteed to be valid
pub struct Nice(NiceValue);
type NiceValue = RangedI8<-20, 19>;

// Bad — `i8` admits invalid values for nice levels
pub type Nice = i8;
```

Prefer enums over bare integers and boolean flags.

```rust
// Good — access mode is constrained by the enum
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AccessMode {
    O_RDONLY = 0,
    O_WRONLY = 1,
    O_RDWR = 2,
}

// Bad — `u8` admits invalid values
pub type AccessMode = u8;
```

Encode invariants in generic parameters where needed.

```rust
impl IoMem<Sensitive> {
    // Good — only unsafe code can write to sensitive MMIO
    pub unsafe fn write_u32(&self, offset: usize, new_val: u32) { /* .. */ }
}

impl IoMem<Insensitive> {
    // Good — safe code can write to insensitive MMIO
    pub fn write_u32(&self, offset: usize, new_val: u32) { /* .. */ }
}

pub enum Sensitive {}
pub enum Insensitive {}
```

Asterinas uses this pattern widely,
for example with newtypes such as `CpuId`
and `AlignedUsize<const N: u16>`.

#### Steps

1. Identify values with restricted domains: modes, flags, permissions, IDs, states, units, ranges, and typestate-like properties.
2. Check whether invalid values can be constructed with the proposed types.
3. Prefer newtypes, enums, const generics, marker types, or trait bounds that encode the invariant at compile time.
4. Require runtime validation at construction boundaries when the invariant comes from userspace, hardware, or serialized data.


See also:
PR [#2265](https://github.com/asterinas/asterinas/pull/2265#discussion_r2266214191)
and [#2514](https://github.com/asterinas/asterinas/pull/2514).
### Prefer enum over trait objects for closed sets (`enum-over-dyn`) {#enum-over-dyn}

When the set of variants is known and closed,
an enum is often preferable to `Box<dyn Trait>`
for both performance and pattern-matching expressiveness.

```rust
// Good — closed set modeled as an enum
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TermStatus {
    Exited(u8),
    Killed(SigNum),
}
```

#### Steps

1. Find new `dyn Trait`, `Box<dyn Trait>`, `Arc<dyn Trait>`, and trait-object-based dispatch.
2. Determine whether the implementer set is closed and known inside the crate or subsystem.
3. Prefer an enum when callers benefit from exhaustive matching, compact representation, or static dispatch.
4. Keep trait objects when third-party extension, plugin-style openness, object safety, or type erasure is the actual requirement.

### Encapsulate fields behind getters (`getter-encapsulation`) {#getter-encapsulation}

Do not make fields public
when a simple getter method would do.
A getter preserves naming flexibility
and leaves room for future invariants.

```rust
// Good — field is private, accessed via getter
pub struct Vma {
    perms: VmPerms,
}

impl Vma {
    pub fn perms(&self) -> VmPerms {
        self.perms
    }
}

// Bad — public field exposes representation
pub struct Vma {
    pub perms: VmPerms,
}
```

#### Steps

1. Inspect new public fields and fields whose visibility was widened.
2. Ask whether external code needs direct mutation or only read access.
3. Prefer private fields with getters for read access so representation and invariants remain changeable.
4. Allow public fields mainly for simple data carriers whose representation is the intended API contract.
