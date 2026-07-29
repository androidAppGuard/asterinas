---
date: 2026-07-27
mode: diff
base: ba2f4aa92
head: 3749ab332
branch: HEAD
---

# Summary

This change correctly moves `statfs()`/`fstatfs()` toward the mounted filesystem instead of the wrapped inode filesystem, which is the right shape for making `tmpfs` visible to filesystem probes.

The top issue is that the new `tmpfs` superblock reports all advertised blocks and inodes as free on every call, even after files or inodes are allocated. That makes the newly exposed `statfs` data internally inconsistent and should be fixed before relying on the capacity fields. The change also needs a syscall-level regression test for the `tmpfs` magic value so the VFS lookup behavior does not silently regress.

The remaining maintainability comments are small cleanup items around import qualification, naming the half-memory policy, and documenting the new public `Path::fs` accessor.

## Maintainability

### `kernel/src/fs/fs_impls/tmpfs/fs.rs` line 3

> ```diff
> +use super::TMPFS_MAGIC;
>  use crate::{
> @@
> -        sb.magic = TMPFS_MAGIC;
> +        sb.magic = super::TMPFS_MAGIC;
> ```

`qualified-fn-imports` (nit): `TMPFS_MAGIC` is imported directly from `super`, so the later `sb.magic = TMPFS_MAGIC` assignment reads like it may be a local constant instead of a value from the parent `tmpfs` module.

**Fix.** Remove the direct import and qualify the use as `super::TMPFS_MAGIC`, or move the constant into this module if it is only meaningful here.

### `kernel/src/fs/fs_impls/tmpfs/fs.rs` line 70

> ```diff
> +fn default_max_blocks() -> usize {
> +    crate::vm::mem_total() / PAGE_SIZE / 2
> +}
> +
> +fn default_max_inodes() -> usize {
> +    crate::vm::mem_total() / PAGE_SIZE / 2
> +}
> ```

`no-magic-number` (minor): The `/ 2` divisor encodes the new `tmpfs` default limit policy, but the meaning is hidden at both `default_max_blocks` and `default_max_inodes`. A reader has to infer that `tmpfs` is being capped at half of total memory.

**Fix.** Name the policy once and reuse it, for example `const DEFAULT_MAX_USAGE_DIVISOR: usize = 2;`, or introduce a shared helper such as `default_max_pages()` that documents the half-memory default.

### `kernel/src/fs/vfs/path/mod.rs` line 104

> ```diff
> +    // Gets the file system of current `Path`.
> +    pub fn fs(&self) -> &Arc<dyn FileSystem> {
> +        self.mount.fs()
> +    }
> ```

`rfc1574-summary` (nit): `Path::fs` is a new public accessor, but it is preceded by a plain `//` comment instead of a rustdoc `///` summary, so generated API docs omit the method’s purpose while neighboring public methods are documented.

**Fix.** Use a rustdoc summary in the local style, for example `/// Returns the file system mounted at this path.`

## Correctness

### `kernel/src/fs/fs_impls/tmpfs/fs.rs` line 57

> ```diff
>         sb.blocks = max_blocks;
>         sb.bfree = max_blocks;
>         sb.bavail = max_blocks;
>         sb.files = max_inodes;
>         sb.ffree = max_inodes;
> ```

Incorrect accounting (major): `TmpFs::sb()` reports every tmpfs block and inode as free on every call. A concrete failure is: mount `tmpfs`, create a file, write one `PAGE_SIZE`, then call `statfs()` or `fstatfs()` on that mount; `f_bfree == f_blocks` and `f_ffree == f_files` still hold because the values are recomputed from `mem_total()` and ignore allocated file pages and created inodes.

**Fix.** Track tmpfs-wide allocated blocks and inodes, or compute them from the live tmpfs inode tree, and report free counts with saturating subtraction, including the root inode and allocated file pages. For example, `sb.bfree`/`sb.bavail` should be based on `max_blocks.saturating_sub(used_blocks)`, and `sb.ffree` should be based on `max_inodes.saturating_sub(used_inodes)`.

### `kernel/src/syscall/statfs.rs` line 32

> ```diff
>         path.fs().sb()
> ...
>         file.path().fs().sb()
> ```

`add-regression-tests` (minor): This changes user-visible `statfs()`/`fstatfs()` results for `tmpfs`, but the commit adds no regression test. Without a syscall-level test, `Path::fs()` can regress back to the wrapped `RamFs` result and still compile.

**Fix.** Add a regression test that mounts `tmpfs` and verifies both pathname and fd based probes return `f_type == 0x0102_1994` through `statfs()` and `fstatfs()`. If this is fixing a tracked issue, include that issue reference in the test comment.
