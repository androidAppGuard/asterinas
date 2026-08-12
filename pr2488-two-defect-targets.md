# PR 2488 Benchmark Case: Two Defect Targets

```yaml
- problem_id: 2488-runqueue-irq-reparent-wakeup
  commit: 56d78ab64965194ad03cb6cde07fd5d98b17129d
  remote: https://github.com/asterinas/asterinas
  source: >
    PR 2488 fixes two LTP hang causes listed in the PR body: run queues can be
    locked without disabling local IRQs, and reparented dead children do not
    wake the reaper/init process. The fixes are commits
    2cee744ed9dfdd70d1097d5747e2c72cc2df63b6 and
    62513ec49c832909ff39f01d590edbe2483a0d48.
  review_mode:
    files:
      - kernel/src/sched/sched_class/mod.rs:396-402
      - ostd/src/task/scheduler/mod.rs:100-108
      - kernel/src/process/exit.rs:99-126
  defects:
    - target:
        kind: file
        path: kernel/src/sched/sched_class/mod.rs
        lines: "396-402"
      persona: development
      grounding: run queues must be locked with local IRQ disabled
      severity: critical
      desc: >
        ClassScheduler::nr_queued_and_running locks each run queue with
        rq.lock() while local IRQs remain enabled. The same run queues can be
        touched from the timer IRQ callback registered by enable_preemption_on_cpu.
        If an IRQ fires while the current context holds a run-queue lock, the
        callback can try to lock the same run queue again and deadlock.
      fix: >
        Make the run-queue spinlock require LocalIrqDisabled, or otherwise
        disable local IRQs before every run-queue lock acquisition so task and
        interrupt contexts cannot re-enter the lock on the same CPU.
      expectation: >
        A valid review must identify that run-queue locks are used from IRQ
        callbacks and therefore must always be acquired with local IRQ disabled;
        merely locking the SpinLock is insufficient.
    - target:
        kind: file
        path: kernel/src/process/exit.rs
        lines: "99-126"
      persona: development
      grounding: wake reaper after moving dead children
      severity: major
      desc: >
        move_children_to_reaper_process moves children from an exiting process
        to a reaper or init process, but it does not wake the new parent's
        children_wait_queue. If some moved children are already dead, init can
        sleep in wait because no child-death notification is delivered after the
        reparenting, so tests such as kill08 can hang waiting for reaping.
      fix: >
        After move_process_children succeeds, call
        reaper_process.children_wait_queue().wake_all(); do the same for the
        fallback init_process path.
      expectation: >
        A valid review must say that moving children to init/reaper must wake
        that process's child wait queue, otherwise already-dead reparented
        children may never be reaped.
```

## Provenance

- PR: https://github.com/asterinas/asterinas/pull/2488
- Problem commit: `56d78ab64965194ad03cb6cde07fd5d98b17129d`
- Fix commits:
  - `2cee744ed9dfdd70d1097d5747e2c72cc2df63b6`
  - `62513ec49c832909ff39f01d590edbe2483a0d48`
- Final PR head: `be2ed1bc777a9f4d8a32e5a28edda184be3e6f85`
- Review comment for defect 1: https://github.com/asterinas/asterinas/pull/2488#discussion_r2405145254
- Defect 2 evidence: PR body plus the `Add wakeups after moving children` fix diff.
