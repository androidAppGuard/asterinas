- problem_id: 2477-clone-reaper-defects
  commit: 702aa7d9eeffec033aff33769c2fd5cc75984262
  remote: https://github.com/asterinas/asterinas
  source: >
    PR-derived from https://github.com/asterinas/asterinas/pull/2477. The PR
    description explicitly identifies five defects: a clone-flag check in the
    wrong layer, incomplete `CloneArgs::check` validation, incomplete
    `clone3()` stack validation, a `find_reaper_process` race, and incorrect
    memory orderings for subreaper state. The final PR commit additionally
    fixes the `set_child_tid` invalid-address panic, as stated by its commit
    message `Don't panic if `set_child_tid` is invalid`. The reviewed snapshot
    is the PR base commit `702aa7d9eeffec033aff33769c2fd5cc75984262`, before
    all three PR commits. The snapshot contains no PR description, review
    response, or fix commit, so the defect targets are leak-free.
  review_mode:
    files:
      - kernel/src/process/clone.rs
      - kernel/src/syscall/clone.rs
      - kernel/src/process/exit.rs
      - kernel/src/process/process/mod.rs
      - kernel/src/thread/task.rs
  defects:
    - target:
        kind: file
        path: kernel/src/process/clone.rs
        lines: "132-137"
      persona: security
      grounding: validate-at-boundaries
      severity: major
      desc: >
        The `CLONE_FS` plus `CLONE_NEWNS` incompatibility check is placed in
        `CloneArgs::for_clone`, which is only used by the legacy `clone`
        syscall. Both `clone` and `clone3` call `clone_child`, and
        `clone_child` invokes the common `CloneArgs::check`, but `clone3`
        constructs `CloneArgs` through `TryFrom<Clone3Args>` and bypasses
        `for_clone`. Consequently, invalid `clone3` flag combinations can reach
        the common clone implementation without this required validation.
      fix: >
        Remove the check from `CloneArgs::for_clone` and perform it in
        `CloneArgs::check`, which is called by `clone_child` for both
        `clone` and `clone3`, as commit
        `07dfd7badd89c8d4d102752433312c1c17fb02c4` does.
      expectation: >
        A reviewer should identify that validation in `for_clone` is not shared
        by `clone3` and require the `CLONE_FS`/namespace compatibility check to
        live in the common `CloneArgs::check` path.

    - target:
        kind: file
        path: kernel/src/process/clone.rs
        lines: "185-225"
      persona: security
      grounding: validate-at-boundaries
      severity: major
      desc: >
        `CloneArgs::check` validates `CLONE_VM` and `CLONE_SIGHAND` only inside
        the `CLONE_THREAD` branch. It therefore accepts `CLONE_SIGHAND` without
        `CLONE_VM`, although the Linux clone contract requires
        `CLONE_VM` whenever `CLONE_SIGHAND` is specified. This invalid flag
        combination is not rejected for either clone entry point once the
        common check is reached.
      fix: >
        Add an independent check that returns `EINVAL` when
        `CLONE_SIGHAND` is set without `CLONE_VM`, as commit
        `07dfd7badd89c8d4d102752433312c1c17fb02c4` does.
      expectation: >
        A reviewer should flag the missing unconditional dependency check and
        require `CLONE_SIGHAND` without `CLONE_VM` to be rejected with
        `EINVAL`.

    - target:
        kind: file
        path: kernel/src/syscall/clone.rs
        lines: "84-124"
      persona: security
      grounding: validate-at-boundaries
      severity: major
      desc: >
        `TryFrom<Clone3Args>` converts `value.stack` directly and only converts
        `value.stack_size` to `Option<NonZeroU64>`. It accepts exactly one of
        the stack address and stack size, and it does not verify that the stack
        range lies in userspace. `clone3` can therefore pass an incomplete or
        invalid stack description into later child-context setup instead of
        returning `EINVAL`.
      fix: >
        Treat stack and stack size as a pair: reject cases where exactly one is
        nonzero, and when both are present validate the start and inclusive end
        addresses with `is_userspace_vaddr`, as commit
        `07dfd7badd89c8d4d102752433312c1c17fb02c4` does.
      expectation: >
        A reviewer should flag the missing `clone3` stack validation and require
        `EINVAL` for a stack address without size, a size without address, or a
        stack range outside userspace.

    - target:
        kind: file
        path: kernel/src/process/exit.rs
        lines: "49-73"
      persona: development
      grounding: atomic-critical-sections
      severity: major
      desc: >
        `find_reaper_process` keeps the current ancestor as a weak reference and
        walks upward by upgrading each parent. If the parent and grandparent
        exit and are reaped concurrently, the grandparent upgrade can fail.
        The loop then terminates and returns `None`, even though a current
        parent chain may still identify the correct reaper. The caller then
        falls back to adopting children into init, which is incorrect for this
        race.
      fix: >
        Retain an upgraded parent `Arc`, upgrade the next ancestor separately,
        and retry from `current_process.parent()` when the parent and
        grandparent disappear concurrently, as commit
        `dcdb0d91d6d72974ccc00b672b6cf248e1453a95` does.
      expectation: >
        A reviewer should flag that a transient failed weak upgrade is treated
        as proof that no reaper exists and require retry logic for concurrent
        parent/grandparent exit and reaping.

    - target:
        kind: whole_change
      persona: development
      grounding: careful-atomics
      severity: major
      desc: >
        The subreaper state uses inconsistent memory orderings. The
        `is_child_subreaper` flag is independent state and does not need
        acquire/release synchronization, while `has_child_subreaper` is
        propagated through the process hierarchy and needs release stores and
        acquire loads to publish and observe the propagated state. The base
        code uses `Relaxed` when assigning `has_child_subreaper` during child
        setup, but uses stronger orderings for the related propagation paths;
        it also uses unnecessary acquire/release orderings for
        `is_child_subreaper`. This fails to express the synchronization
        protocol consistently and can allow a child to observe stale
        subreaper ancestry state.
      fix: >
        Use `Relaxed` for the independent `is_child_subreaper` accesses and
        `Release`/`Acquire` for publishing and observing `has_child_subreaper`,
        including the child setup path in `kernel/src/process/clone.rs`.
      expectation: >
        A reviewer should identify the distinction between the independent
        subreaper flag and the propagated ancestry flag, and require relaxed
        access for the former plus release/acquire synchronization for the
        latter. This target spans `kernel/src/process/clone.rs` and
        `kernel/src/process/process/mod.rs`.

    - target:
        kind: file
        path: kernel/src/thread/task.rs
        lines: "54-62"
      persona: development
      grounding: propagate-errors
      severity: major
      desc: >
        Child startup checks only that `set_child_tid` is numerically within the
        userspace virtual-address range, then calls `write_val(...).unwrap()`.
        An address can be in that range but unmapped or unwritable, causing the
        user-memory write to return an error and the child task to panic. This
        is a user-controlled invalid pointer reaching a kernel `unwrap`.
      fix: >
        Attempt the `set_child_tid` write but ignore or otherwise handle its
        error without panicking, as final PR commit
        `7a3e0cdc06c1d053df69e8fbda2aad6c341bef62` does with
        `let _ = current_userspace!().write_val(...)`.
      expectation: >
        A reviewer should flag the reachable `unwrap()` after only a virtual
        address-range check and require invalid or unwritable `set_child_tid`
        addresses to be handled without a kernel panic.
