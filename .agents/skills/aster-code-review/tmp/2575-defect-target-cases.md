- problem_id: 0415-sched-syscall-error-defects
  commit: cef527f372afeb78b5648048f7aaa631207e59bc
  remote: https://github.com/asterinas/asterinas
  source: >
    PR-derived from https://github.com/asterinas/asterinas/pull/2575. The PR
    fixes scheduler syscall compatibility bugs in the pre-fix snapshot
    `cef527f372afeb78b5648048f7aaa631207e59bc`: user-memory faults from
    `sched_*` paths were collapsed to `EINVAL`, `sched_setattr` could allocate
    an unbounded buffer from a user-controlled `sched_attr.size`, and
    `sched_getattr` did not implement Linux-compatible size handling for short
    or oversized user buffers. The reviewed snapshot is before fixing commits
    `46a5b037dce367838f31dd9fb52e5337762eb680` and
    `9d9a48be687338b886e4c9b824f95a5d46b1984e`, so the targets are leak-free.
  review_mode:
    files:
      - kernel/src/syscall/sched_getattr.rs
      - kernel/src/syscall/sched_setattr.rs
      - kernel/src/syscall/sched_setparam.rs
      - kernel/src/syscall/sched_setscheduler.rs
      - kernel/src/syscall/sched_getparam.rs
  defects:
    - target:
        kind: file
        path: kernel/src/syscall/sched_setattr.rs
        lines: "15-20"
      persona: development
      grounding: preserve user-copy fault errors
      severity: major
      desc: >
        `sys_sched_setattr` maps every failure from
        `read_linux_sched_attr_from_user` to `EINVAL`. That erases real user
        memory faults, so a non-null invalid pointer that should report
        `EFAULT` is returned as `EINVAL`; it also hides compatibility errors
        such as `E2BIG` from oversized `sched_attr` input with non-zero trailing
        bytes.
      fix: >
        Reject a null address with `EINVAL`, then propagate errors from
        `read_linux_sched_attr_from_user` unchanged. The same rule should apply
        to other `sched_*` user-copy paths instead of converting all copy
        failures to `EINVAL`.
      expectation: >
        A reviewer should flag the blanket `map_err(|_| EINVAL)` around a
        user-copy helper and require syscall-visible errors such as `EFAULT`
        and `E2BIG` to be preserved.

    - target:
        kind: file
        path: kernel/src/syscall/sched_getattr.rs
        lines: "153-158"
      persona: security
      grounding: bound user-controlled sched_attr sizes
      severity: major
      desc: >
        `read_linux_sched_attr_from_user` trusts `attr.size` when computing
        `additional_size` and allocates `vec![0; additional_size]`. A user can
        pass a very large `sched_attr.size`, forcing an unbounded kernel
        allocation before the syscall returns `E2BIG`, which can panic or
        exhaust memory.
      fix: >
        Validate the user size before allocation, accepting only Linux-supported
        sizes from `SCHED_ATTR_SIZE_VER0` through `PAGE_SIZE`. For oversized
        input, write back the kernel struct size and return `E2BIG` without
        allocating a user-controlled buffer.
      expectation: >
        A reviewer should identify the user-controlled allocation and require a
        fixed upper bound before any allocation or trailing-byte scan.

    - target:
        kind: file
        path: kernel/src/syscall/sched_getattr.rs
        lines: "176-187"
      persona: development
      grounding: implement sched_getattr compatible writeback
      severity: major
      desc: >
        `write_linux_sched_attr_to_user` accepts any `user_size` and writes only
        `min(sizeof(LinuxSchedAttr), user_size)` bytes. Thus undersized buffers
        such as `SCHED_ATTR_SIZE_VER0 - 1` can succeed instead of returning
        `EINVAL`, and oversized buffers keep stale non-zero bytes after the
        kernel struct instead of being zero-filled as Linux-compatible
        `sched_getattr` expects.
      fix: >
        Reject `user_size < SCHED_ATTR_SIZE_VER0` or `user_size > PAGE_SIZE`
        with `EINVAL`, set `attr.size` to the kernel struct size capped by the
        user size, and use compatible writeback that zero-fills any user buffer
        tail beyond the kernel struct.
      expectation: >
        A reviewer should check both bounds and tail handling for variable-size
        user ABI structures, not only whether the initial struct bytes are
        copied successfully.
