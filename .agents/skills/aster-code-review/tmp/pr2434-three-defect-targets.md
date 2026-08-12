# PR 2434 Benchmark Case: Three Defect Targets

```yaml
- problem_id: 2434-named-pipe-open-nonblock-status-flags
  commit: 7e7ba43cdfc572cd2ddeecc86a5951bbd200d692
  remote: https://github.com/asterinas/asterinas
  source: >
    PR 2434 fixes three named-pipe defects present before the PR: FIFO open
    does not wait for the peer endpoint, read/write cannot honor each fd's
    O_NONBLOCK flag, and named-pipe status flags are not per-fd. The PR body
    states these three issues directly, and final head
    66194a964af102206886424bd1840af5c2c197a6 refactors NamedPipe into
    per-open handles to fix them.
  review_mode:
    files:
      - kernel/src/fs/named_pipe.rs
      - kernel/src/fs/ramfs/fs.rs
      - kernel/src/fs/path/mod.rs
      - kernel/src/fs/pipe.rs
      - kernel/src/fs/pipe.rs
      - kernel/src/fs/inode_handle/mod.rs
      - kernel/src/fs/inode_handle/mod.rs
  defects:
    - target:
        kind: file
        path: kernel/src/fs/named_pipe.rs
        lines: "14-45"
      persona: development
      grounding: FIFO open must block until the peer endpoint is present
      severity: major
      desc: >
        NamedPipe stores one PipeReader and one PipeWriter from creation time
        and exposes itself as O_RDWR. Opening the FIFO through Path::open only
        builds a normal InodeHandle; there is no per-open reader/writer handle
        and no wait in open. Therefore blocking open(O_RDONLY) can return even
        when no writer has opened the FIFO, and blocking open(O_WRONLY) can
        return even when no reader has opened it.
      fix: >
        Add a NamedPipe::open(access_mode, status_flags) path that creates a
        per-open handle and waits for the opposite endpoint for blocking
        O_RDONLY/O_WRONLY opens, while allowing O_RDWR to succeed immediately.
      expectation: >
        A valid review must say that FIFO open semantics are wrong because open
        returns before both read and write ends are present in blocking mode; it
        should request blocking in open based on access mode and peer presence.
    - target:
        kind: file
        path: kernel/src/fs/ramfs/fs.rs
        lines: "552-600"
      persona: development
      grounding: named-pipe read/write ignore the fd's O_NONBLOCK flag
      severity: major
      desc: >
        RamFS dispatches NamedPipe read/write directly to the shared
        NamedPipe object. NamedPipe::read and NamedPipe::write take no
        StatusFlags, and InodeHandle::read/write do not pass their per-fd
        status_flags into FileLike/FileIo. As a result, read/write behavior is
        determined by the shared pipe endpoints, not by the file descriptor that
        issued the operation, so O_NONBLOCK on a FIFO fd is not reliably honored.
      fix: >
        Route named-pipe I/O through a FileIo handle whose read/write methods
        receive the current InodeHandle status_flags, and choose try_read/try_write
        for O_NONBLOCK or wait_events for blocking descriptors.
      expectation: >
        A valid review must identify that named-pipe read/write need access to
        the caller fd's status_flags; otherwise O_NONBLOCK cannot control whether
        the operation returns EAGAIN or blocks.
    - target:
        kind: file
        path: kernel/src/fs/pipe.rs
        lines: "50-123,158-234"
      persona: development
      grounding: status_flags must be per file descriptor, not shared by the pipe object
      severity: major
      desc: >
        PipeReader and PipeWriter each store status_flags inside the shared pipe
        endpoint object. A FIFO inode has one shared NamedPipe with shared reader
        and writer endpoints, while each open fd has its own InodeHandle
        status_flags. If two descriptors open the same FIFO with different flags,
        such as one blocking reader and one nonblocking reader, storing the flag
        on the shared endpoint cannot represent both descriptors correctly.
      fix: >
        Keep status_flags on InodeHandle/per-open handles and pass them into
        named-pipe read/write. Do not store FIFO nonblocking behavior as mutable
        state in the shared PipeReader/PipeWriter object.
      expectation: >
        A valid review must state that status_flags for a named pipe must be
        per-fd; a shared NamedPipe/PipeReader/PipeWriter flag makes descriptors
        interfere with each other and cannot support simultaneous blocking and
        nonblocking opens.
```

## Why These Are The Right Defects

- They are exactly the three defects listed in the PR 2434 description.
- The problem snapshot predates the PR's named-pipe refactor and still has a
  single shared `NamedPipe { reader, writer }`.
- The final PR head fixes them by introducing per-open named-pipe handles and by
  passing `StatusFlags` from `InodeHandle` into `FileIo::read/write`.

## Provenance

- PR: https://github.com/asterinas/asterinas/pull/2434
- Problem commit: `7e7ba43cdfc572cd2ddeecc86a5951bbd200d692`
- First PR fix commit: `7e408f0a715ad990d6873dee7197cc0933bab7fc`
- Final PR head: `66194a964af102206886424bd1840af5c2c197a6`
