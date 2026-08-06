- problem_id: 0408-pr-2290-defect-targets
  commit: c6a6e66aaca9635e36d99e47ed87edd6d4b69f87
  source: >
    PR-derived from https://github.com/asterinas/asterinas/pull/2290. Files mode
    uses the PR base commit `c6a6e66aaca9635e36d99e47ed87edd6d4b69f87`, where
    all three defects are present before PR commits `84d5265a1`, `9004fb490`,
    and `f946894d2` fix them. This snapshot contains the buggy CI expressions,
    the `SOCK_SEQPACKET` debug assertion, and the `pause_timeout` signal-wait
    race, but does not include the PR description or fix commits that name the
    defects, so the reviewed files are leak-free.
  review_mode:
    files:
      - .github/workflows/test_x86.yml
      - kernel/src/net/socket/unix/stream/connected.rs
      - kernel/src/process/signal/pause.rs
  defects:
    - target:
        kind: file
        path: .github/workflows/test_x86.yml
        lines: "84-100"
      persona: development
      grounding: "Preserve explicit false configuration values"
      severity: major
      desc: >
        The workflow passes `release` and `enable_kvm` to the test action with
        `${{ matrix.release || true }}` and `${{ matrix.enable_kvm || true }}`.
        In GitHub Actions expressions, an explicit boolean `false` is falsy, so
        `false || true` evaluates to `true`. Matrix entries that deliberately set
        `release: false` for debug builds or `enable_kvm: false` for non-KVM
        runs are therefore silently converted back to enabled/release runs, and
        CI does not execute the configuration declared by the matrix.
      fix: >
        Preserve the distinction between an omitted value and an explicit
        `false` at both test-action call sites. The PR fix uses
        `${{ !contains(matrix.release, 'false') }}` and
        `${{ !contains(matrix.enable_kvm, 'false') }}` so omitted values default
        to true while explicit false values reach the action.
      expectation: >
        A reviewer should flag that the `|| true` fallback overwrites explicit
        `false` values for `release` and `enable_kvm`, preventing debug and
        KVM-disabled CI jobs from actually running as requested.

    - target:
        kind: file
        path: kernel/src/net/socket/unix/stream/connected.rs
        lines: "202"
      persona: development
      grounding: "Allow legal zero-length SOCK_SEQPACKET messages"
      severity: major
      desc: >
        `Connected::try_read` permits zero-length reads for `SOCK_SEQPACKET`, but
        the final invariant is `debug_assert!(is_empty || read_tot_len != 0)`.
        `is_empty` describes the caller's receive buffer, not whether the socket
        type allows zero-length packets. A valid empty `SOCK_SEQPACKET` message
        can therefore reach this assertion with `is_empty == false` and
        `read_tot_len == 0`, causing a deterministic debug-build panic instead
        of accepting the legal packet.
      fix: >
        Encode the protocol exception in the assertion, as PR commit
        `84d5265a160e53686acff6c61ae6a624b48043d5` does by changing it to
        `debug_assert!(is_seqpacket || read_tot_len != 0)`, or otherwise allow
        zero-length `SOCK_SEQPACKET` messages without panicking.
      expectation: >
        A reviewer should flag that the assertion rejects legal zero-length
        `SOCK_SEQPACKET` receives and ask for the invariant to be based on
        `is_seqpacket` or an equivalent protocol-aware condition.

    - target:
        kind: file
        path: kernel/src/process/signal/pause.rs
        lines: "152-175"
      persona: development
      grounding: "Close the signal-registration to wait race"
      severity: major
      desc: >
        `Waiter::pause_timeout` installs the POSIX signal waker and immediately
        calls `self.wait()`, only checking `posix_thread.has_pending()` after the
        wait returns. If a signal is already pending, or becomes pending after
        waker registration but before the thread actually blocks, there may be no
        later wakeup to make `self.wait()` return. The post-wait pending check is
        then reached only after timeout or some unrelated wakeup, so calls such
        as `ppoll` can miss `SIGINT` and return timeout instead of `EINTR`.
      fix: >
        After `set_signalled_waker`, recheck `posix_thread.has_pending()` before
        entering `self.wait()`. If a signal is pending, clear the registered
        waker and return `EINTR`; otherwise wait and clear the waker after the
        wait returns, as PR commit `9004fb490cf8f9a9c42b410afd482a868a51eccd`
        does.
      expectation: >
        A reviewer should flag the lost-wakeup race between registering the
        signal waker and blocking, and require a pending-signal recheck plus
        waker cleanup on the early-return path.
