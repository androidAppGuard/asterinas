- problem_id: 0407-kill-fixes-defects
  commit: 50eaffc7314d5ef2f4a16cb0e2437cc0010c01ee
  remote: https://github.com/asterinas/asterinas
  source: >
    PR-derived from https://github.com/asterinas/asterinas/pull/2488. The PR
    fixes two LTP hang/deadlock defects: scheduler run queues can be locked
    without IRQs disabled even though `enable_preemption_on_cpu` makes them
    reachable from interrupt callbacks, and moved children do not wake the new
    reaper/init process, so waiters such as LTP `kill08` can sleep forever. The
    reviewed snapshot is the PR starting point
    `50eaffc7314d5ef2f4a16cb0e2437cc0010c01ee`, before the fixing commits
    `2cee744ed9dfdd70d1097d5747e2c72cc2df63b6` and
    `62513ec49c832909ff39f01d590edbe2483a0d48`, so the targets are leak-free.
  review_mode:
    files:
      - kernel/src/sched/sched_class/mod.rs
      - kernel/src/process/exit.rs
  defects:
    - target:
        kind: file
        path: kernel/src/sched/sched_class/mod.rs
        lines: "65-67"
      persona: development
      grounding: lock run queues with local IRQs disabled
      severity: major
      desc: >
        `ClassScheduler::rqs` is a plain `SpinLock<PerCpuClassRqSet>`, so callers
        can lock a run queue without the type system requiring local IRQs to be
        disabled. The scheduler installs preemption callbacks with
        `enable_preemption_on_cpu`, and those callbacks can access the same run
        queues from interrupt context. If task context holds the run queue lock
        with IRQs enabled and the local interrupt callback tries to take it
        again, the CPU can deadlock.
      fix: >
        Make the run queue lock require the `LocalIrqDisabled` marker, and existing callers
        must hold an IRQ-disable guard before locking, and call sites that
        already disabled IRQs can use `lock()` directly.
      expectation: >
        A reviewer should identify that per-CPU run queues are shared between
        task and interrupt/preemption callback contexts, and require the lock to
        enforce local IRQ disabling for every acquisition, not just selected
        call sites.

    - target:
        kind: file
        path: kernel/src/process/exit.rs
        lines: "116-126"
      persona: development
      grounding: wake waiters after reparenting children
      severity: major
      desc: >
        `move_children_to_reaper_process` moves all children from an exiting
        process to a subreaper, but it returns without waking the
        new parent's `children_wait_queue`. A process already blocked in
        `wait*()` sleeps on that queue until a child status change wakes it; if
        dead children were just reparented to it, the waiter may never re-check
        its child list and reap them. This can leave LTP `kill08`-style waits
        stuck forever.
      fix: >
        After a successful `move_process_children`, wake the chosen reaper's
        `children_wait_queue`; also wake init after the fallback reparenting.
      expectation: >
        A reviewer should flag that reparenting creates newly waitable children
        for the reaper/init process and must wake that process's child wait
        queue on both successful paths.
