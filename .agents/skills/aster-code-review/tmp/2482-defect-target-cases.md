- problem_id: 0409-getrandom-boundary-semantics
  commit: b606e3456c43924f4b465900b51e2349a554c0df
  remote: https://github.com/asterinas/asterinas
  source: >
    PR-derived from https://github.com/asterinas/asterinas/pull/2482. The PR
    description explicitly identifies three `getrandom` defects in the base
    implementation: invalid flags are not rejected, a user-controlled `count`
    drives an unbounded kernel allocation, and short writes are not allowed.
    The fixing commit is `933f7494deca558c198e712d284d18d9e12835f7`
    (`Fix some `getrandom` behavior`). Files mode checks PR base commit
    `b606e3456c43924f4b465900b51e2349a554c0df`, whose `getrandom.rs` matches
    the PR body's linked snapshot `294c55d0dfa5e5784729548f9764b26e608c18ff`
    for this file. The reviewed file contains no PR description or fix code, so
    the defects are leak-free.
  review_mode:
    files:
      - kernel/src/syscall/getrandom.rs
  defects:
    - target:
        kind: file
        path: kernel/src/syscall/getrandom.rs
        lines: "6-8"
      persona: security
      grounding: validate-at-boundaries
      severity: major
      desc: >
        `sys_getrandom` parses user-supplied flags with
        `GetRandomFlags::from_bits_truncate(flags)`. Unknown bits are silently
        discarded instead of being rejected. A syscall boundary must validate
        user-controlled flags before trusting them internally; otherwise
        callers can pass invalid flag combinations and receive success for a
        request Linux would reject with `EINVAL`.
      fix: >
        Parse with `GetRandomFlags::from_bits(flags)` and return `EINVAL` when
        it returns `None`, as fixing commit
        `933f7494deca558c198e712d284d18d9e12835f7` does. Also reject invalid
        known combinations such as `GRND_INSECURE | GRND_RANDOM`.
      expectation: >
        A reviewer should flag `from_bits_truncate` at the syscall boundary and
        require invalid `getrandom` flags, including unsupported bits, to be
        rejected instead of masked away.

    - target:
        kind: file
        path: kernel/src/syscall/getrandom.rs
        lines: "12-18"
      persona: security
      grounding: validate-at-boundaries
      severity: major
      desc: >
        The syscall allocates `vec![0u8; count]` directly from the
        user-controlled `count` argument. There is no upper bound or streaming
        through the user buffer, so a large `count` can force an unbounded kernel
        allocation and panic or exhaust memory. User-supplied sizes must be
        validated at syscall boundaries before being used to allocate kernel
        memory.
      fix: >
        Avoid allocating a kernel buffer sized by `count`. Create a bounded
        userspace writer with `ctx.user_space().writer(buf, count)?` and pass it
        to the random device so bytes are generated directly into userspace.
      expectation: >
        A reviewer should flag the `vec![0u8; count]` allocation as unbounded
        allocation from a user-controlled syscall argument and require bounded
        validation or direct streaming to the user writer.

    - target:
        kind: file
        path: kernel/src/syscall/getrandom.rs
        lines: "14-22"
      persona: security
      grounding: validate-at-boundaries
      severity: major
      desc: >
        The implementation first fills a kernel buffer, records `read_len`, and
        then writes the entire `buffer.as_slice()` of length `count` to
        userspace with `write_bytes`. If only part of the requested user buffer
        can be written, this full-buffer write turns the operation into an error
        instead of returning the number of bytes already produced. The PR
        identifies that `getrandom` should permit short writes; therefore the
        user buffer must be represented by a writer whose partial progress is
        visible to the random device.
      fix: >
        Replace the intermediate full-size kernel buffer and final full
        `write_bytes` call with `ctx.user_space().writer(buf, count)?`, then let
        `device::Random::getrandom` or `device::Urandom::getrandom` write
        directly into that writer and return the actual byte count.
      expectation: >
        A reviewer should flag that writing the whole `count`-sized buffer after
        generating `read_len` bytes prevents valid short-write behavior and ask
        for direct userspace-writer based copying that reports actual progress.
