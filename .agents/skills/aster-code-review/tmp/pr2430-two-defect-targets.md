# PR 2430 Benchmark Case: Two Defect Targets

```yaml
- problem_id: 0412-read-cstring-netlink-defects
  commit: 46aa437c8738e72a47510e764cb2b6eed8032706
  remote: https://github.com/asterinas/asterinas
  source: >
    PR 2430 fixes two pre-existing ReadCString-related bugs: user C-string
    reads return the wrong error when the search reaches the caller limit, and
    netlink attribute parsing mishandles strings/errors by not consuming the
    whole attribute or reporting parse errors correctly. These are the two
    problems described in the PR body and fixed by final head
    ea608661ffca5f2c2bd8f5391be3384602e5a160.
  review_mode:
    files:
      - kernel/src/context.rs:292-306
      - kernel/src/net/socket/netlink/route/message/attr/addr.rs:61-96
      - kernel/src/net/socket/netlink/route/bound.rs:61-73
  defects:
    - target:
        kind: file
        path: kernel/src/context.rs
        lines: "292-306"
      persona: development
      grounding: distinguish ENAMETOOLONG from EFAULT when reading user C strings
      severity: major
      desc: >
        read_cstring_with_max_len always returns EFAULT when no NUL byte is
        found before max_len. That is wrong when the user pointer is valid and
        the string simply exceeds the caller-provided length limit; that case
        should return ENAMETOOLONG. EFAULT is only appropriate when the scan
        reaches the end of user address space before finding NUL.
      fix: >
        Clamp the reader length to MAX_USERSPACE_VADDR - vaddr. If no NUL is
        found, return ENAMETOOLONG when the caller's max_len was reached, and
        EFAULT when the userspace address limit was reached first.
      expectation: >
        A valid review must identify that the missing-NUL error code depends on
        why scanning stopped: caller length limit means ENAMETOOLONG, while user
        address-space exhaustion means EFAULT.
    - target:
        kind: file
        path: kernel/src/net/socket/netlink/route/message/attr/addr.rs
        lines: "61-96"
      persona: development
      grounding: netlink string attribute parsing must consume the whole attribute
      severity: major
      desc: >
        AddrAttr::read_from uses read_cstring_with_max_len(payload_len) for
        LABEL. If a NUL appears before payload_len, the reader stops early and
        leaves the cursor inside the attribute, so later parsing starts at the
        wrong position. If no NUL appears, the helper returns an error even
        though Linux allows such attributes. The caller then silently ignores
        most parse errors in bound.rs instead of reporting a netlink error
        segment.
      fix: >
        Use a helper that can read until NUL or the attribute end, skip any
        unread attribute bytes, and represent parse failures with a full-read
        result so the caller can continue at the next segment and report an
        error segment where appropriate.
      expectation: >
        A valid review must say that netlink attribute parsing cannot leave the
        reader cursor in the middle of an attribute and must not require NUL for
        attributes where Linux accepts missing NUL; parse errors should be
        consumed/skipped and reported through the netlink error path.
```

## Why This Replaces The Earlier Version

- The earlier `read_cstring.rs` allocation and init-stack NUL checks are valid
  review comments on PR 2430, but they are not the two problems described by
  the PR body.
- This version targets the actual PR-level defects: user C-string error-code
  semantics and netlink attribute parsing/skip/error-reporting semantics.

## Provenance

- PR: https://github.com/asterinas/asterinas/pull/2430
- Problem commit: `46aa437c8738e72a47510e764cb2b6eed8032706`
- Final PR head: `ea608661ffca5f2c2bd8f5391be3384602e5a160`
