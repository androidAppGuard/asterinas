# Functions & Methods

### Avoid boolean arguments (`no-bool-args`) {#no-bool-args}

A boolean parameter that selects between
two behaviors signals the function does two things.
Split it into two functions
or use a typed enum.

```rust
// Good — two separate functions
fn read(&self, buf: &mut [u8]) -> Result<usize> { ... }
fn read_nonblocking(&self, buf: &mut [u8]) -> Result<usize> { ... }

// Good — typed enum
enum ReadMode { Blocking, NonBlocking }
fn read(&self, buf: &mut [u8], mode: ReadMode) -> Result<usize> { ... }

// Bad — boolean argument
fn read(&self, buf: &mut [u8], blocking: bool) -> Result<usize> { ... }
```

#### Steps

1. Inspect new function and method signatures for boolean parameters.
2. Determine whether the boolean selects between two behaviors or merely passes a factual property to lower-level code.
3. Require separate functions when callers should choose between named operations.
4. Require a typed enum or option type when one parameter represents a mode that may grow or needs to be self-documenting at call sites.


See also:
_Clean Code_, Chapter 3 "Flag Arguments".
### Use block expressions to scope temporary state (`block-expressions`) {#block-expressions}

Use block expressions
when temporary variables are only needed
to produce one final value.
This keeps temporary state local
and avoids leaking one-off names into outer scope.

```rust
// Good — intermediate values are scoped to the block
let socket_addr = {
    let bytes = read_bytes_from_user(addr, len as usize)?;
    parse_socket_addr(&bytes)?
};
connect(socket_addr)?;

// Bad — temporary variables leak into outer scope
let bytes = read_bytes_from_user(addr, len as usize)?;
let socket_addr = parse_socket_addr(&bytes)?;
connect(socket_addr)?;
```

#### Steps

1. Look for temporary variables that are used only to compute one later value.
2. Check whether those names leak into a wider scope than their purpose requires.
3. Prefer a block expression when it groups setup, validation, or conversion into one resulting value.
4. Do not force a block when the intermediate names are reused later or when extraction into a helper would be clearer.

### Minimize nesting (`minimize-nesting`) {#minimize-nesting}

Minimize nesting depth.
Code nested more than three levels deep
should be reviewed for refactoring opportunities.
Each nesting level multiplies the reader's cognitive load.

Techniques for flattening nesting:
- Early returns and guard clauses for error paths.
- `let...else` to collapse `if let` chains.
- The `?` operator for error propagation.
- `continue` to skip loop iterations.
- Extracting the nested body into a helper function.

The normal/expected code path
should be the first visible path;
error and edge cases
should be handled and dismissed early.

```rust
pub(crate) fn init() {
    let Some(framebuffer_arg) = boot_info().framebuffer_arg else {
        warn!("Framebuffer not found");
        return;
    };
    // ... main logic at the top level
}
```

#### Steps

1. Scan changed functions for nesting deeper than about three levels.
2. Identify whether outer levels are error handling, optional matching, loop filtering, or the main expected path.
3. Prefer guard clauses, `let...else`, `?`, `continue`, or helper extraction to keep the normal path at the left margin.
4. Preserve clarity when nesting expresses a real hierarchy; do not flatten code into scattered state mutations.


See also:
PR [#2877](https://github.com/asterinas/asterinas/pull/2877#discussion_r2685861741).
### Introduce explaining variables (`explain-variables`) {#explain-variables}

Break down complex expressions
by assigning intermediate results to well-named variables.
An explaining variable turns an opaque expression
into self-documenting code:

```rust
// Good — intent is clear
let is_page_aligned = addr % PAGE_SIZE == 0;
let is_within_range = addr < max_addr;
debug_assert!(is_page_aligned && is_within_range);

// Bad — reader must parse the whole expression
debug_assert!(addr % PAGE_SIZE == 0 && addr < max_addr);
```

#### Steps

1. Find dense boolean conditions, arithmetic expressions, iterator chains, bit operations, and assertions in the changed code.
2. Ask whether a reader can understand the expression's intent without mentally evaluating every operator.
3. Require well-named intermediate variables for meaningful subconditions or computed quantities.
4. Keep compact expressions when the operation is idiomatic and the extracted name would add no new meaning.

See also:
_The Art of Readable Code_, Chapter 8 "Breaking Down Giant Expressions";
PR [#2083](https://github.com/asterinas/asterinas/pull/2083#discussion_r2512772091)
and [#643](https://github.com/asterinas/asterinas/pull/643#discussion_r1497243812).
