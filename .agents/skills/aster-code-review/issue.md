# Motivation

When running and analyzing the 21 defects in benchmark problems 400-406 (log link and log analysis: `0963c9ea15438642eb5c7f97c34d9a595487f85d`), we found that 14 defects were not recalled. At least three of these missed defects can be attributed to a lack of domain knowledge. For the remaining missed defects, we cannot determine with confidence whether they were caused by insufficient domain knowledge.

## Illustrative Examples

1. Unrecalled defect in problem 400: [Allow legal zero-length `SOCK_SEQPACKET` messages](https://github.com/asterinas/asterinas/pull/2290/changes/84d5265a160e53686acff6c61ae6a624b48043d5#diff-e9b3e25b0e16514ddb6836b722b3f0a86bf8a70ca398ca9e3d746976002d618bR202)

   According to the relevant man-pages, a zero-length packet is a legal message, so the caller's receive buffer may be non-empty while `is_empty == true` is still valid. `recv(2)` explicitly states that zero-size datagrams are allowed.

   <img width="500" alt="Image" src="https://github.com/user-attachments/assets/8661020c-9d2a-426c-9f59-825e7341b87a" />

   The Asterinas kernel comments do not document this semantic detail. During review, `aster-code-review` also did not query socket-related domain knowledge, so it missed this defect.

2. Unrecalled defect in problem 403: [Write supported version for `capget` when the requested version is unsupported](https://github.com/asterinas/asterinas/pull/2390/changes/5a49190969bdb366ba167c32c3fddec78d56156c)

   For the `capget` syscall, when the user specifies an unsupported capability version, the kernel should write the supported version back to user space, as described in the man-pages.

   <img width="500" alt="Image" src="https://github.com/user-attachments/assets/9a0964dd-ef17-4860-a0fc-16cb9f3a4184" />

   The Asterinas kernel comments do not explain the semantics of the `capget` syscall, so the agent could not understand the syscall behavior and missed this defect.

   <img width="500" alt="Image" src="https://github.com/user-attachments/assets/ace1896e-eee4-4310-bbee-cdd75ccb548c" />

3. Unrecalled defect in problem 403: [Reject empty pathname for `openat`](https://github.com/asterinas/asterinas/pull/2390/changes/0c7f4a4f7636c897a8a401ee4004f5351b933209)

   According to the Linux kernel documentation, in general, syscalls ending with `at` do not allow an empty pathname unless the `AT_EMPTY_PATH` flag is provided.

   From [the documentation](https://elixir.bootlin.com/linux/v6.0.9/source/Documentation/filesystems/path-lookup.rst):

   ```plain
   It is tempting to describe the second kind as starting with a
   component, but that isn't always accurate: a pathname can lack both
   slashes and components, it can be empty, in other words.  This is
   generally forbidden in POSIX, but some of those "``*at()``" system calls
   in Linux permit it when the ``AT_EMPTY_PATH`` flag is given.  For
   example, if you have an open file descriptor on an executable file you
   can execute it by calling `execveat() <execveat_>`_ passing
   the file descriptor, an empty path, and the ``AT_EMPTY_PATH`` flag.
   ```

   Neither the Asterinas kernel comments nor `aster-code-review` contained this domain knowledge, so the agent missed this defect.

# Solution 1

`SKILL.md` already contains an instruction to query domain knowledge, but the instruction is too coarse-grained: it does not explain how or where to search, and it is placed in the wrong section.

```plain
## Verification (step 6)

For each comment, isolate the key premise it rests on
— especially an external-system fact (Linux/POSIX behaviour, the System V ABI, Rust semantics).
Try to **refute** it:
re-read the cited code and consult an authoritative source.
Assign a verdict:

- **confirmed** — keep the comment unchanged.
- **uncertain** — keep it, but prefix `problem` with `(unverified) `.
- **refuted** — remove the comment,
  and append it to a `## Retracted by verification` list at the foot of the file with a one-line reason.

Remove **only** on confident refutation;
an unsure check is `uncertain`, not `refuted`.
This is the only step that may remove a comment, and only false positives.
```

To address this, we added domain-knowledge lookup instructions to each persona pass by updating `pass_contract.md`.

Details: `f9d031f589d1e1736aec80380229bed46eb8ed9f`

## Result

Two of the three unrecalled defects above were successfully recalled. The `reject empty pathname for openat` defect was still not recalled (log link and log analysis: `b612dc9c8fe8a98e0b17141d1515a239ba3085ce`).

The reason this defect was still missed is that the instructions only provided a general pointer to the Linux source tree. For VFS/pathname domain knowledge, this was too coarse-grained. As a result, the agent only searched Linux man-pages and failed to find the relevant domain knowledge in `Documentation/filesystems/path-lookup.rst`:

https://elixir.bootlin.com/linux/v6.0.9/source/Documentation/filesystems/path-lookup.rst

# Solution 2

We further refined `pass_contract.md` to tell the agent how to search the documentation tree, following a human-like process: when Linux man-pages do not fully specify the behavior, search the documentation tree by first identifying the relevant subsystem directory, then identifying the file in that directory that describes the needed domain knowledge.

Details: `b2ca133875fce8176e7bab8ed343720e6c34cebe`

## Result

All three unrecalled defects above were successfully recalled.

# Discussion

These motivating examples show that domain knowledge can improve the agent's recall. However, I do not think the current solution is the best strategy. It is a refined workaround designed to avoid large changes to the current project structure.

In my view, the ideal solution is to analyze and extract this relevant domain knowledge in advance, then make it available to the agent when needed. This would avoid requiring the agent to discover, analyze, and summarize domain knowledge during review, which introduces uncertainty into the analysis process.
