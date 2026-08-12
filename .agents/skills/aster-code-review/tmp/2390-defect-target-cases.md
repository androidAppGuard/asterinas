- problem_id: 411-pr-podman-small-issues
  commit: 3b0666449f8f4dc68e339cb7ee0646b45bf21fb1
  remote: https://github.com/asterinas/asterinas
  source: >
    PR-derived from https://github.com/asterinas/asterinas/pull/2390. The PR
    description explicitly identifies three Podman-related issues, and each is
    fixed by one of the three commits in the PR:
    `9ce444d54c8fd1800656e454114d9306d61a92b7`,
    `5a49190969bdb366ba167c32c3fddec78d56156c`, and
    `0c7f4a4f7636c897a8a401ee4004f5351b933209`. Files mode checks the PR base
    commit `3b0666449f8f4dc68e339cb7ee0646b45bf21fb1`, before those fixes. The
    reviewed files contain the defects but no PR description, review response,
    or fix commit, so the targets are leak-free.
  review_mode:
    files:
      - kernel/src/syscall/madvise.rs
      - kernel/src/syscall/capget.rs
      - kernel/src/syscall/open.rs
  defects:
    - target:
        kind: file
        path: kernel/src/syscall/madvise.rs
        lines: "35-50"
      persona: development
      grounding: "Unsupported MADV behavior must not panic"
      severity: major
      desc: >
        `MadviseBehavior` defines `MADV_NOHUGEPAGE`, but the match in
        `sys_madvise` has no arm for it. The value therefore reaches the
        catch-all `_ => todo!()` branch. A Podman call using
        `madvise(..., MADV_NOHUGEPAGE)` causes a kernel panic even though this
        Asterinas build does not support huge pages and can safely treat the
        advice as a no-op.
      fix: >
        Add an explicit `MADV_NOHUGEPAGE` arm that emits a warning and returns
        success without changing mappings, as commit
        `9ce444d54c8fd1800656e454114d9306d61a92b7` does. Do not route this
        recognized but unsupported advice through `todo!()`.
      expectation: >
        A reviewer should flag the reachable `todo!()` panic for the declared
        `MADV_NOHUGEPAGE` value and require a non-panicking unsupported-operation
        behavior, such as warning and returning success.

    - target:
        kind: file
        path: kernel/src/syscall/capget.rs
        lines: "20-49"
      persona: development
      grounding: "Match capget version negotiation and null-data semantics"
      severity: major
      desc: >
        `sys_capget` immediately returns `EINVAL` when the requested capability
        version is unsupported, without writing
        `LINUX_CAPABILITY_VERSION_3` back through the header pointer. It also
        unconditionally writes the capability result to `cap_user_data_addr`,
        so a null data pointer cannot return success. The Linux capget contract
        uses an unsupported-version call to report the supported version, and
        permits a null data pointer for the version-query case. The base
        implementation therefore breaks Podman's capability probing protocol.
      fix: >
        When the header version is unsupported, write
        `LINUX_CAPABILITY_VERSION_3` to the header and return success if
        `cap_user_data_addr == 0`; otherwise return `EINVAL`. Also return
        success early when the supported version is used with a null data
        pointer, before attempting to write capability data, as commit
        `5a49190969bdb366ba167c32c3fddec78d56156c` does.
      expectation: >
        A reviewer should flag both missing parts of the version-query contract:
        the supported version must be written back on an unsupported request,
        and a null data pointer must not be dereferenced or rejected when the
        call is only querying the ABI version.

    - target:
        kind: file
        path: kernel/src/syscall/open.rs
        lines: "21-40"
      persona: development
      grounding: "Reject empty pathname for openat"
      severity: major
      desc: >
        `sys_openat` reads the pathname and passes it directly to
        `FsPath::new` and the resolver. With an empty pathname, it does not
        return the required `ENOENT` error at the syscall boundary and instead
        relies on lower-level path handling, which does not provide the Linux
        `openat` behavior expected by Podman. `openat` has no
        `AT_EMPTY_PATH` option that would make an empty pathname valid.
      fix: >
        Check `path.is_empty()` immediately after reading and logging the
        pathname, then return `ENOENT` before constructing `FsPath`, as commit
        `0c7f4a4f7636c897a8a401ee4004f5351b933209` does.
      expectation: >
        A reviewer should flag that an empty pathname reaches generic path
        resolution and require `sys_openat` to return `ENOENT` explicitly before
        resolution.
