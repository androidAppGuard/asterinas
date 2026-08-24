- problem_id: 0408-procfs-bug-fix-defects
  commit: ff021e0b89811c92069950a5a96ef41f9860de0b
  remote: https://github.com/asterinas/asterinas
  source: >
    PR-derived from https://github.com/asterinas/asterinas/pull/2553. The PR
    body explicitly lists five procfs defects in snapshot
    `ff021e0b89811c92069950a5a96ef41f9860de0b`: inconsistent lock order between
    the process table and procfs cached entries, an atomic-mode break from file
    table notifications into procfs cache updates, incorrect `/proc/[pid]`
    results after exec in a non-main thread, stale `/proc/.../fd` results after
    file-table unshare, and stale `/proc/[pid]/task/[tid]` directories after a
    thread exits. The reviewed snapshot is the linked pre-fix snapshot, before
    fixing commits `a1a6660a9c863ded0ab0a5e98eaaaf8020b047fb`,
    `3b039611a77fdeb92d2e5bb4fb9bc63949e07487`, and
    `ecf61b7223528e99ecfadfe5689412ba67623ca6`, so the defect targets are
    leak-free.
  review_mode:
    files:
      - kernel/src/fs/procfs/mod.rs
      - kernel/src/fs/procfs/pid/mod.rs
      - kernel/src/fs/procfs/pid/task/fd.rs
      - kernel/src/fs/procfs/pid/task/mod.rs
      - kernel/src/fs/procfs/pid/task/mountinfo.rs
  defects:
    - target:
        kind: file
        path: kernel/src/fs/procfs/mod.rs
        lines: "139-209"
      persona: development
      grounding: keep procfs lock order consistent
      severity: major
      desc: >
        Procfs takes locks in opposite orders for the same shared state.
        `PidEvent::Exit` runs while the process table is locked and then writes
        `cached_children`, so that path is process table -> cached entries. But
        `populate_children` first locks `cached_children` and then iterates
        `process_table::process_table_mut()`, making the order cached entries ->
        process table. Concurrent process exit and `/proc` directory population
        can deadlock.
      fix: >
        Use a single lock order for root procfs process entries. Taking the process
        table before `cached_children` when dynamic PID entries are populated or
        looked up, and by keeping static entries separate from the process-table
        critical section.
      expectation: >
        A reviewer should identify both lock acquisition paths and require the
        process table and procfs cached-entry locks to be acquired in one
        consistent order.

    - target:
        kind: file
        path: kernel/src/fs/procfs/pid/task/fd.rs
        lines: "34-55"
      persona: development
      grounding: do not call procfs cache observers from file-table spinlocks
      severity: major
      desc: >
        `/proc/[pid]/fd` registers its procfs inode as a file-table observer.
        File descriptor close paths notify these observers while mutating the
        file table, which is protected by a spin lock; the observer then writes
        `cached_children`, a mutex-backed procfs cache. Taking a mutex from this
        file-table atomic context can break atomic-mode constraints and sleep
        while a spin lock is held.
      fix: >
        Remove the file-table observer mechanism for procfs fd entries. Rebuild
        or validate `/proc/.../fd` cached children by reading the current file
        table from procfs lookup/readdir paths.
      expectation: >
        A reviewer should flag that fd close notifications can enter procfs cache
        mutation while the file table spin lock is held, and require procfs not
        to rely on observer callbacks from that atomic context.

    - target:
        kind: file
        path: kernel/src/fs/procfs/pid/mod.rs
        lines: "29-42"
      persona: development
      grounding: process-level procfs entries must not pin the old main thread
      severity: major
      desc: >
        `PidDirOps::new_inode` captures `process_ref.main_thread()` once and
        embeds that thread in the process-level `/proc/[pid]` directory. After a
        non-main thread successfully executes a new program, it becomes the
        process's main thread. Existing `/proc/[pid]` entries such as
        `mountinfo`, `stat`, `status`, and `fd` can still read through the old
        cached thread and report stale or wrong per-thread state.
      fix: >
        Represent process-level procfs entries without a pinned thread, and
        resolve `process_ref.main_thread()` when the file is read or the fd
        directory is populated.
      expectation: >
        A reviewer should identify that process-level procfs state caches the
        main thread too early and require it to resolve the current main thread
        after exec, especially for non-main-thread exec.

    - target:
        kind: file
        path: kernel/src/fs/procfs/pid/task/fd.rs
        lines: "102-131"
      persona: development
      grounding: procfs fd symlinks must track current file descriptors
      severity: major
      desc: >
        Each `/proc/[pid]/fd/N` inode stores an `Arc<dyn FileLike>` captured when
        the procfs entry is created. If the process later unshares its file table
        or closes and reopens the same descriptor, the cached procfs symlink can
        continue to point at the old file object and return the wrong target.
      fix: >
        Store the task identity and numeric file descriptor in the procfs fd
        symlink, not the old `FileLike`. On `read_link`, look up the current file
        descriptor in the current file table and refresh cached fd entries when
        the descriptor disappears or its access mode changes.
      expectation: >
        A reviewer should flag that caching `Arc<dyn FileLike>` makes
        `/proc/.../fd/N` stale across unshare or descriptor reuse, and require
        lookup against the current file table.

    - target:
        kind: file
        path: kernel/src/fs/procfs/pid/task/mod.rs
        lines: "194-206"
      persona: development
      grounding: remove task procfs dentries on thread exit
      severity: major
      desc: >
        `/proc/[pid]/task` populates and caches one child directory per live
        thread, but it never registers for thread-exit events and never removes
        cached TID entries. Once a thread exits, a previously populated
        `/proc/[pid]/task/[tid]` directory can remain visible from the cache even
        though the thread no longer exists.
      fix: >
        Register the task directory as an observer of the process task set and
        remove the cached child named by the exiting TID when a `TidEvent::Exit`
        arrives.
      expectation: >
        A reviewer should identify that cached task directories need an invalidation
        path on thread exit and require `/proc/[pid]/task/[tid]` entries to be
        removed when their thread exits.
