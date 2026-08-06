# Layout

### Organize code for top-down reading (`top-down-reading`) {#top-down-reading}

A source file should read from top to bottom.
Start with high-level entry points and core flow.
Move implementation details downward
so readers can understand the big picture first
before diving into low-level helpers.

Within each visibility group (e.g., a module),
order methods so that callers appear before callees where possible,
enabling the file to be read top to bottom.
Place public methods before private helpers.

#### Steps

1. Open each changed file as a reader would and identify the entry points, main types, and helper details.
2. Check whether the file introduces the high-level flow before low-level helper functions or private machinery.
3. Within an `impl` or module, prefer public or caller methods before private callees when dependencies allow it.
4. Request reordering when the current layout forces readers to jump around before understanding the core behavior.

### Group statements into logical paragraphs (`logical-paragraphs`) {#logical-paragraphs}

Within functions,
group related statements into logical paragraphs
separated by blank lines.
Each paragraph should represent one sub-step
of the function's overall purpose.

For long functions,
add a one-line summary comment
at the start of each paragraph
when the paragraph intent is not obvious.

#### Steps

1. Review changed functions with enough statements to have multiple conceptual steps.
2. Group the statements mentally into setup, validation, lookup, mutation, notification, cleanup, and return phases.
3. Require blank lines where adjacent phases are currently run together.
4. Ask for a short paragraph comment only when the grouped step is non-obvious even after naming and extraction are considered.
