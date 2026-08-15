# Why the agent did not reach the right Linux VFS source

## Conclusion

The failure is not simply "the agent did not have a primary-source instruction". It did: `scripts/pass_contract.md` tells every pass to consult authoritative sources and lists Linux man pages plus Linux source for syscall or VFS behavior. Evidence: `scripts/pass_contract.md:51-58`; the same text was injected into an actual pass prompt at `log/log_link_domainknowledge/log_0403.txt:370-377`.

The real problem is that the instruction is too coarse for VFS/pathname domain knowledge. It names `man7.org` first and gives only the generic Linux source root, so the agent can satisfy the contract by checking man pages even when the decisive rule lives in Linux VFS documentation or `fs/namei.c`. In `log_0403`, the path-related searches went to `path_resolution(7)` and `pathname(7)`, and the final checked references were only `capget(2)`, `madvise(2)`, and `pathname(7)`. Evidence: `log/log_link_domainknowledge/log_0403.txt:8262-8273`, `log/log_link_domainknowledge/log_0403.txt:9084-9086`.

## What the correct domain source says

For pathname/VFS behavior, `Documentation/filesystems/path-lookup.rst` is the right conceptual route. It explains that pathnames are split into "everything else" and the final component, that final components are syscall-specific, and that Linux pathname walking is mostly implemented in `fs/namei.c`. Evidence from Linux v6.0.9: `path-lookup.rst:60-70`, `path-lookup.rst:88-90`.

For the parent-directory write checks, the decisive implementation source is `fs/namei.c`. Linux v6.0.9 has `may_create()` requiring `inode_permission(..., MAY_WRITE | MAY_EXEC)` on the parent directory, and `may_delete()` doing the same for deletes. Evidence: `fs/namei.c:2916-2937`, `fs/namei.c:2959-2980`. The VFS operations then route through those helpers: `vfs_mknod()` calls `may_create()`, `vfs_link()` calls `may_create()`, `vfs_rmdir()` and `vfs_unlink()` call `may_delete()`, and `vfs_rename()` calls `may_delete()`/`may_create()` on the old and new parents. Evidence: `fs/namei.c:3867-3874`, `fs/namei.c:4458-4471`, `fs/namei.c:4075-4079`, `fs/namei.c:4206-4211`, `fs/namei.c:4677-4692`.

One correction: the statement "Linux man pages do not contain this semantic" is too strong for the high-level parent-write-permission rule. `mknod(2)`, `link(2)`, `rename(2)`, and `unlink(2)` all mention `EACCES` for missing write access/permission on the containing or parent directory. Evidence: fetched man7 pages show `mknod.2.html:149`, `link.2.html:159`, `rename.2.html:234`, `unlink.2.html:142`. What man pages do not provide is the unified VFS model: final-component handling, dentry/parent relationships, and the `may_create()`/`may_delete()` implementation path.

## Why the current contract was insufficient

1. The source list is not wrong, but it is under-specified. `pass_contract.md` says "Linux man pages ... and Linux source ... for syscall or VFS behavior", but it does not say when man pages are insufficient, nor does it mention `Documentation/filesystems/path-lookup.rst` or `fs/namei.c` as the VFS/pathname route. Evidence: `scripts/pass_contract.md:55-58`.

2. The URL points at `elixir.bootlin.com/linux/latest/source/`, not the kernel version under review. The user pointed to Linux v6.0.9, and the relevant code/documentation should be version-pinned when the reviewed code cites or emulates that version. Evidence: the contract uses `latest` at `scripts/pass_contract.md:56-57`; Asterinas code in the same review area cites Linux v6.0.9 for permission bits at `log/original_log/log_0405.txt:16330`.

3. The contract has no escalation rule. If a man page gives only syscall-level `EACCES` text or no exact semantic, the reviewer is not explicitly required to continue to Linux documentation and `fs/namei.c`. The only fallback says that if a source cannot be checked, keep the claim narrow or uncertain. Evidence: `scripts/pass_contract.md:64-70`.

4. Verification is designed to remove false positives, not recover missed domain knowledge. The skill's verification step assigns `confirmed`/`uncertain`/`refuted` to each existing comment and says this is the only step that may remove a comment, only false positives; it does not require searching for missing VFS invariants after a shallow source check. Evidence: `SKILL.md:190-199`.

5. The actual logs show the failure mode. For the `openat` pathname target, the agent queried man7 `path_resolution(7)` and `pathname(7)`, then produced a real but adjacent finding about `to_string_lossy()` and invalid UTF-8 path bytes. It missed the expected empty-path rule: `openat` should return `ENOENT` before generic path resolution. Evidence: expected target at `log/log_link_domainknowledge/log_0403.txt:9199-9201`; searches at `log/log_link_domainknowledge/log_0403.txt:8264-8267`; produced finding at `log/log_link_domainknowledge/log_0403.txt:9432-9434`.

6. For the VFS permission comments in `log_0405`, the final review identified missing parent `MAY_WRITE` checks on `Path::mknod`, `Path::link`, `Path::rename`, `Path::unlink`, and `Path::rmdir`, but those comments are not source-grounded in `path-lookup.rst` or `fs/namei.c`. Evidence: produced comments at `log/original_log/log_0405.txt:18607-18675`; a repository-wide log search for `path-lookup`/`Documentation/filesystems` found no matching lookup record in the logs inspected.

## Contract fix direction

`pass_contract.md` should keep man pages, but add the empirical documentation
navigation step explicitly. Since there is no universal Linux Documentation
routing table, the contract should describe how to use `Documentation/` as a
subsystem map before consulting implementation source:

```md
For Linux kernel behavior that is not fully specified by man pages, navigate the
version-matched Linux `Documentation/` tree as a subsystem map before jumping
into implementation source. Identify the owning subsystem directory, read its
index/overview and focused `.rst` files for the domain model, terminology,
invariants, and source entry points, then verify the concrete rule in the
matching implementation source.

For VFS/pathname semantics, do not stop at man pages.
If the review involves pathname lookup, `*at()` path resolution, empty
pathname, trailing slash, final-component behavior, dentry parent semantics,
mount/namei behavior, or create/delete/link/rename permission checks, consult
the version-matched filesystem documentation and implementation:

- `Documentation/filesystems/path-lookup.rst` for the conceptual pathname model.
- `fs/namei.c` for concrete helpers such as `may_create()`, `may_delete()`,
  `vfs_link()`, `vfs_rename()`, `vfs_unlink()`, and `vfs_mknod()`.

Use the Linux version relevant to the reviewed code when known. If unknown, use
the version cited by local comments/tests first; use current Linux source only
as a fallback. Man pages are still useful for syscall-facing behavior and error
descriptions, but they are not sufficient evidence for VFS internal pathname
semantics.
```

This would make the primary-source instruction precise enough that "checked
man7" no longer counts as sufficient evidence for this VFS/pathname class,
while making the more general instruction about `Documentation/` a navigation
method rather than a fake universal index.
