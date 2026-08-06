# Naming

### Be descriptive (`descriptive-names`) {#descriptive-names}

Choose names that convey meaning at the point of use.
Avoid single-letter names and ambiguous abbreviations.
Prefer full words over cryptic shorthand
so that readers do not need surrounding context
to understand a variable's purpose.
Prefer names that are as short as possible
while still being unambiguous at the point of use.

#### Steps

1. Review every new or renamed variable, function, type, field, constant, module, and test.
2. Read each name at its call site or use site without relying on distant context.
3. Flag single letters, vague words, and unexplained abbreviations unless the scope is tiny and conventional.
4. Prefer the shortest name that still communicates the domain role, not the implementation mechanics.

### Be accurate (`accurate-names`) {#accurate-names}

Avoid confusing names.
If a name can be misread
to imply the wrong meaning, behavior, or side effects,
it must be corrected immediately.

```rust
// Good — clearly a count
nr_deleted_watches: usize,
// Bad — looks like a collection
// rather than a numeric counter
deleted_watches: usize
```

Choose verbs that reflect the actual work being done.

```rust
impl PciCommonDevice {
    // Good — implies an MMIO read is involved
    pub fn read_command(&self) -> Command { /* .. */ }
    // Bad — looks like a plain field access
    pub fn command(&self) -> Command { /* .. */ }
}
```

```rust
mod char_device {
    // Good — implies an O(n) collection pass
    pub fn collect_all() -> Vec<Arc<dyn Device>> { /* .. */ }
    // Bad — sounds like an accessor returning a reference
    pub fn get_all() -> Vec<Arc<dyn Device>> { /* .. */ }
}
```

#### Steps

1. Compare each name with the value's type, ownership, cost, side effects, and behavior.
2. Flag names that misstate the value kind, operation cost, side effects, or mutability.
3. Check verbs especially carefully: `get`, `read`, `collect`, `take`, `set`, and `try_` should match the actual operation.
4. Require renaming immediately when a plausible reader could infer the wrong semantics.


See also:
PR [#1488](https://github.com/asterinas/asterinas/pull/1488#discussion_r1825441287)
and [#2964](https://github.com/asterinas/asterinas/pull/2964#discussion_r2789739882).
### Encode units and important attributes in names (`encode-units`) {#encode-units}

When the type does not encode the unit,
the name must.
Kernel code deals with bytes, pages, frames,
nanoseconds, ticks, and sectors —
ambiguous units are a source of real bugs.

```text
// Good — unit is unambiguous
timeout_ns
offset_bytes
size_pages
delay_ms

// Bad — unit is ambiguous
timeout
offset
size
delay
```

Where the language's type system can enforce units (e.g., newtypes),
prefer that.
Where it cannot, the name must carry the information.

#### Steps

1. Find numeric values whose type does not encode units or representation.
2. Check addresses, sizes, offsets, lengths, timeouts, ticks, pages, frames, sectors, and counts for ambiguous names.
3. Prefer a newtype when unit safety matters across interfaces.
4. Otherwise require a suffix or name component such as `_bytes`, `_pages`, `_ns`, `_ticks`, or `_sectors`.


See also:
PR [#2796](https://github.com/asterinas/asterinas/pull/2796#discussion_r2646889913).
### No magic number (`no-magic-number`) {#no-magic-number}

Numeric literals must be meaningful at the point of use.
When a number represents a non-local invariant,
an external contract,
or a domain-specific meaning
beyond its immediate arithmetic value,
give that meaning a name.
Use a constant,
typed value,
enum variant,
or helper function,
whichever best expresses the invariant.

```rust
// Good — the flag's meaning is explicit.
const NEEDS_ACK_FLAG: u8 = 0b0000_0100;
let needs_ack = (packet_flags & NEEDS_ACK_FLAG) != 0;

// Bad — the reader must infer why this bit is special.
let needs_ack = (packet_flags & 0b0000_0100) != 0;
```

Prefer deriving related values from the named source
instead of repeating the same number in multiple places.
If the name alone does not explain where the value comes from,
add a short comment or cite the relevant specification.

Do not introduce names for numbers
whose meaning is already obvious locally,
such as `0`, `1`, or `2`
in ordinary arithmetic,
indexing,
small ranges,
or direct comparisons.

#### Steps

1. Scan added numeric literals, bit masks, shifts, limits, sizes, delays, and protocol values.
2. Decide whether each number's meaning is obvious from local arithmetic or whether it encodes a rule, unit, external contract, or invariant.
3. Require a named constant, enum variant, typed value, or helper for non-local meanings.
4. Ask for a source comment when the name explains the role but not where the value comes from.

### Use assertion-style boolean names (`bool-names`) {#bool-names}

Boolean variables and functions
should read as assertions of fact.
Use `is_`, `has_`, `can_`, `should_`, `was_`,
or `needs_` prefixes.
Never use negated names
(`is_not_empty`, `no_error`);
prefer the positive form
(`is_empty`, `ok` or `succeeded`).
A bare name like `found`, `done`, or `ready`
is acceptable when the context is unambiguous.

```rust
// Good — reads as an assertion
fn is_page_aligned(&self) -> bool { ... }
fn has_permission(&self, perm: Permission) -> bool { ... }
let can_read = mode.is_readable();

// Bad — verb suggests an action, not a query
fn check_permission(&self, perm: Permission) -> bool { ... }
// Bad — negated name
let is_not_empty = !buf.is_empty();
```

#### Steps

1. Find new boolean variables, methods, fields, and predicate closures.
2. Read each boolean use as an assertion in conditions and assignments.
3. Require positive predicate names with `is_`, `has_`, `can_`, `should_`, `was_`, or `needs_` when context alone is not enough.
4. Reject negated names that force double negatives at use sites; rename to the positive form and invert the expression if needed.


See also:
PR [#1488](https://github.com/asterinas/asterinas/pull/1488#discussion_r1841827039).
### Format error messages consistently (`error-message-format`) {#error-message-format}

Start with a lowercase letter
(unless the first word is a proper noun or identifier).
Be specific:
prefer "`len` is too large" over "the argument is invalid".

For system call errors,
follow the style and descriptions in Linux man pages.

#### Steps

1. Review added or changed user-visible error strings and syscall-related diagnostics.
2. Check that messages start lowercase unless the first word is an identifier or proper noun.
3. Require the message to name the specific invalid value, state, or operation rather than saying only that something failed.
4. For syscall behavior, compare wording and meaning with the relevant Linux man page.
