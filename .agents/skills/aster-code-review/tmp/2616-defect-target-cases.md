- problem_id: 0416-evdev-fixes-defects
  commit: 70eda539dfade526c28d44e6cb60c056c56cc06c
  remote: https://github.com/asterinas/asterinas
  source: >
    PR-derived from https://github.com/asterinas/asterinas/pull/2616. The PR
    body identifies multiple evdev defects in snapshot
    `70eda539dfade526c28d44e6cb60c056c56cc06c`: evdev files reported
    themselves as seekable, read-side counters could become stale after a
    user-copy failure, short read buffers skipped required checks, full buffers
    usually failed to queue `SYN_DROPPED`, opened-file cleanup could deadlock
    against event delivery, and char-device registration could be reached from
    an atomic input-core path. The reviewed snapshot is before the fixing PR
    commits through `ed3416a2530ce9fc1a2bfad9f87786f644584853`, so the
    targets are leak-free.
  review_mode:
    files:
      - kernel/comps/input/src/lib.rs
      - kernel/src/device/evdev/file.rs
      - kernel/src/device/evdev/mod.rs
      - kernel/src/util/ring_buffer.rs
  defects:
    - target:
        kind: file
        path: kernel/src/device/evdev/file.rs
        lines: "249-252"
      persona: development
      grounding: evdev files are not seekable
      severity: major
      desc: >
        `EvdevFile::check_seekable` returns `Ok(())`, so `lseek()` on an evdev
        character device can succeed or be treated as supported. Linux evdev
        files are stream-like input files and should reject seeking with
        `ESPIPE`.
      fix: >
        Return `ESPIPE` from `check_seekable` for evdev files, as the PR does,
        while keeping `is_offset_aware()` false.
      expectation: >
        A reviewer should flag that evdev must not advertise seek support and
        require the syscall-visible error to be `ESPIPE`.

    - target:
        kind: file
        path: kernel/src/device/evdev/file.rs
        lines: "167-178"
      persona: development
      grounding: keep evdev counters consistent after consuming an event
      severity: major
      desc: >
        `process_events` pops an event from the ring buffer, then writes it to
        user memory before decrementing `event_count` and `packet_count`. If
        `writer.write_val` fails after the pop, the event is already consumed
        but the counters still say it is available, leaving poll/read state
        stale and possibly reporting input that can never be read.
      fix: >
        Update packet/count state immediately after a successful pop, before
        the fallible user write. The PR removes the redundant event counter and
        decrements the packet count before `write_val`.
      expectation: >
        A reviewer should notice that ring-buffer consumption and availability
        counters must be updated atomically with respect to the pop, not after
        a fallible user-memory write.

    - target:
        kind: file
        path: kernel/src/device/evdev/file.rs
        lines: "212-217"
      persona: development
      grounding: reject too-short evdev read buffers
      severity: major
      desc: >
        `read_at` returns `Ok(0)` whenever the user buffer cannot hold a full
        `EvdevEvent`. For a nonzero buffer shorter than one event, Linux evdev
        returns `EINVAL`; this early return also bypasses nonblocking packet
        checks that should run before a zero-length read result is accepted.
      fix: >
        Return `EINVAL` when `requested_bytes != 0` but `max_events == 0`, then
        perform the nonblocking packet-availability check before allowing a true
        zero-length read to return `0`.
      expectation: >
        A reviewer should distinguish a real zero-length read from a too-small
        event buffer and require the evdev ABI checks to run in the Linux order.

    - target:
        kind: file
        path: kernel/src/device/evdev/mod.rs
        lines: "145-175"
      persona: development
      grounding: report dropped input when the evdev buffer is full
      severity: major
      desc: >
        When `producer.push(timed_event)` fails because the ring buffer is full,
        the code immediately tries to push a `SYN_DROPPED` event into the same
        full buffer. That usually fails too, so readers receive neither the
        dropped notification nor a reliable indication that earlier events were
        lost.
      fix: >
        Detect the almost-full condition before the normal event push, clear or
        make room for stale events while holding the producer side, and queue
        `SYN_DROPPED` before continuing with new input, as the PR's
        `free_len() <= 1` path does.
      expectation: >
        A reviewer should flag that a recovery path entered only after the
        buffer is already full cannot reliably enqueue `SYN_DROPPED`.

    - target:
        kind: file
        path: kernel/src/device/evdev/mod.rs
        lines: "124-130"
      persona: development
      grounding: do not drop EvdevFile while holding opened_files
      severity: major
      desc: >
        `pass_events` holds `opened_files` while upgrading a `Weak<EvdevFile>`
        to a temporary `Arc`. If that temporary is the file's last strong
        reference, dropping it at the end of the loop runs `EvdevFile::drop`,
        which calls `detach_closed_files` and tries to lock `opened_files`
        again. That can deadlock event delivery.
      fix: >
        Do not store weak file handles that need upgrading while the device lock
        is held. Store shared file-inner objects in `opened_files` and remove a
        closed file directly in `Drop` without scanning/upgrading other entries.
      expectation: >
        A reviewer should connect the `Weak::upgrade` lifetime under
        `opened_files` with `EvdevFile::drop`'s cleanup path and require a lock
        design that cannot recursively acquire the same lock.

    - target:
        kind: file
        path: kernel/src/device/evdev/mod.rs
        lines: "262-269"
      persona: development
      grounding: do not take sleeping locks from input-core atomic context
      severity: major
      desc: >
        `EvdevHandlerClass::connect` calls `register`, which locks the char
        device registry mutex, and then locks `EVDEV_DEVICES`. But input handler
        `connect` callbacks are invoked while the input core is protected by a
        spin lock. Taking mutex-backed registry locks from that atomic path can
        break atomic-mode constraints.
      fix: >
        Make the input core lock sleepable, as the PR does by changing it from
        `SpinLock<InputCore>` to `Mutex<InputCore>`, or otherwise move evdev
        char-device registration outside the spin-locked input-core path.
      expectation: >
        A reviewer should trace `InputCore::{register_device,register_handler_class}`
        calling `connect` under the input-core lock and reject mutex acquisition
        from a spin-lock/atomic context.
