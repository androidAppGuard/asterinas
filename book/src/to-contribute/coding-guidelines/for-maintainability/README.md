# For Maintainability

*Is the shape of the change sound, and will the next reader understand it without archaeology?*

This is the index of the **maintainability** guidelines.
Each subsection is its own page,
and each entry below links a stable `short-name` to its guideline,
with a one-line gist so a reader (or a review tool) can grasp the guideline before opening it.

## Index

**[Design](design.md)**
- [`single-responsibility`](design.md#single-responsibility): Keep each module, type, or function focused on one reason to change; apply when a unit mixes responsibilities or abstraction levels.
- [`dry`](design.md#dry): Represent each piece of knowledge once; apply when the same rule or pattern recurs three or more times.
- [`information-hiding`](design.md#information-hiding): Keep implementation details behind the smallest useful interface; apply when designing or widening a module or API boundary.
- [`open-closed`](design.md#open-closed): Extend stable modules through existing interfaces; apply when adding behavior to an established module with a concrete extension need.
- [`least-surprise`](design.md#least-surprise): Make names, types, and APIs behave as Rust and Linux users expect; apply when introducing or changing an API, operation, or term.
- [`coupling-cohesion`](design.md#coupling-cohesion): Keep module dependencies small and each module focused on one purpose; apply when splitting or connecting components.
- [`consistency`](design.md#consistency): Use the existing convention for similar code; apply when choosing among otherwise equivalent designs.
- [`rust-native`](design.md#rust-native): Use idiomatic Rust abstractions instead of C-style conventions; apply when adapting Linux designs to Rust.

**[Process](process.md)**
- [`imperative-subject`](process.md#imperative-subject): Write every commit subject in the imperative mood, <=72 chars, verb-first, with identifiers in backticks; apply when creating or editing commit messages.
- [`atomic-commits`](process.md#atomic-commits): Keep each commit to one logical change; apply when staging a commit and separate unrelated work.
- [`refactor-then-feature`](process.md#refactor-then-feature): Put preparatory refactoring in earlier commit(s); apply when a feature depends on structural changes.
- [`focused-prs`](process.md#focused-prs): Keep a pull request on one topic and verify CI before review; apply when preparing a pull request.

**[Naming](naming.md)**
- [`descriptive-names`](naming.md#descriptive-names): Choose names that convey meaning at the point of use; apply when naming variables, functions, types, or other symbols.
- [`accurate-names`](naming.md#accurate-names): Choose names that reflect actual meaning, behavior, and side effects; apply when naming or renaming a symbol.
- [`no-magic-number`](naming.md#no-magic-number): Give non-obvious numeric rules, limits, masks, or external values a semantic name; apply when a literal carries domain meaning.
- [`encode-units`](naming.md#encode-units): Put the unit in a name when the type does not encode it; apply when naming byte, page, time, tick, or sector quantities.
- [`bool-names`](naming.md#bool-names): Name booleans as positive assertions such as `is_`, `has_`, or `can_`, not negations; apply when naming boolean variables or functions.
- [`error-message-format`](naming.md#error-message-format): Start errors lowercase, be specific, and follow Linux man-page style for syscall errors; apply when writing user-visible syscall error messages.

**[Layout](layout.md)**
- [`top-down-reading`](layout.md#top-down-reading): Put entry points and core flow before implementation details; apply when ordering items within a source file.
- [`logical-paragraphs`](layout.md#logical-paragraphs): Group related statements into blank-line-separated sub-steps; apply when organizing statements inside a function.

**[Comments](comments.md)**
- [`explain-why`](comments.md#explain-why): Use comments to explain intent rather than restate code; apply when a non-obvious reason needs recording, otherwise rewrite unclear code.
- [`design-decisions`](comments.md#design-decisions): Record the rationale and alternatives for non-obvious choices; apply when code selects a data structure, locking strategy, or behavior that needs explanation.
- [`cite-sources`](comments.md#cite-sources): Cite the governing specification or algorithm source; apply when implementing external-contract behavior or a non-trivial algorithm.

**[Rust-Specific](rust-specific/)**
- [Naming](rust-specific/naming.md)
    - [`camel-case-acronyms`](rust-specific/naming.md#camel-case-acronyms): Use Rust CamelCase with title-cased acronyms such as `Nvme`; apply when naming types.
    - [`closure-fn-suffix`](rust-specific/naming.md#closure-fn-suffix): End callable variables holding closures or function pointers with `_fn`; apply when binding such a value.
- [Crates & Modules](rust-specific/crates-and-modules.md)
    - [`workspace-deps`](rust-specific/crates-and-modules.md#workspace-deps): Declare shared dependencies in `[workspace.dependencies]` and use `.workspace = true` in members; apply when adding a dependency used by multiple crates.
    - [`module-docs`](rust-specific/crates-and-modules.md#module-docs): Start each major module with `//!` documentation covering its purpose, key types, and neighbors; apply when adding or expanding a major component.
    - [`narrow-visibility`](rust-specific/crates-and-modules.md#narrow-visibility): Start items private and widen visibility only for an actual consumer; apply when choosing visibility for a new or changed item.
    - [`qualified-fn-imports`](rust-specific/crates-and-modules.md#qualified-fn-imports): Call imported free functions, statics, and constants through their parent module; apply when importing those items, not types, traits, or enum variants.
- [Types & Traits](rust-specific/types-and-traits.md)
    - [`rust-type-invariants`](rust-specific/types-and-traits.md#rust-type-invariants): Encode domain constraints with newtypes, enums, or generics; apply when a value has invariants that the type system can enforce.
    - [`enum-over-dyn`](rust-specific/types-and-traits.md#enum-over-dyn): Prefer an `enum` over `Box<dyn Trait>` for a known, closed variant set; apply when the alternatives are not extensible.
    - [`getter-encapsulation`](rust-specific/types-and-traits.md#getter-encapsulation): Expose a getter instead of a public field; apply when callers need access but representation or future invariants may change.
- [Functions & Methods](rust-specific/functions-and-methods.md)
    - [`no-bool-args`](rust-specific/functions-and-methods.md#no-bool-args): Replace behavior-selecting boolean parameters with separate functions or a typed enum; apply when a function has a flag argument.
    - [`block-expressions`](rust-specific/functions-and-methods.md#block-expressions): Scope temporary variables in a block when they only produce one final value; apply when one-off state would otherwise leak into the outer scope.
    - [`minimize-nesting`](rust-specific/functions-and-methods.md#minimize-nesting): Flatten nesting beyond about three levels with guards, `let...else`, `?`, or extraction; apply when the normal path is obscured by error or edge cases.
    - [`explain-variables`](rust-specific/functions-and-methods.md#explain-variables): Name intermediate results of complex expressions; apply when the expression's intent is not obvious at a glance.
- [Attributes & Macros](rust-specific/attributes-and-macros.md)
    - [`expect-dead-code`](rust-specific/attributes-and-macros.md#expect-dead-code): Permit `#[expect(dead_code)]` only for simple counterpart code with clear semantics and a concrete planned use; apply when intentionally adding temporarily unused code.
    - [`alphabetical-attrs`](rust-specific/attributes-and-macros.md#alphabetical-attrs): Sort outer attributes and derive traits alphabetically, with `#[derive(...)]` last; apply when an item has multiple outer attributes.
    - [`narrow-lint-suppression`](rust-specific/attributes-and-macros.md#narrow-lint-suppression): Suppress a lint at the narrowest applicable scope; apply whenever a lint needs an expectation or suppression.
    - [`macros-as-last-resort`](rust-specific/attributes-and-macros.md#macros-as-last-resort): Prefer functions and generics over macros; apply when choosing an abstraction and use a macro only if the type system cannot express it.
- [Comments](rust-specific/comments.md)
    - [`rfc1574-summary`](rust-specific/comments.md#rfc1574-summary): Make the first doc line one concise sentence, using a third-person verb for functions and a noun phrase for types, modules, or fields; apply when documenting an item.
    - [`comment-punctuation`](rust-specific/comments.md#comment-punctuation): End full-sentence comments with terminal punctuation; apply whenever a comment is a complete sentence.
    - [`backtick-identifiers`](rust-specific/comments.md#backtick-identifiers): Wrap identifiers in doc comments with backticks or rustdoc links; apply when referring to code symbols in API documentation.
    - [`no-impl-in-docs`](rust-specific/comments.md#no-impl-in-docs): Describe an API's behavior and usage rather than its implementation; apply when writing or updating doc comments.

No **path-specific** guidelines yet.
