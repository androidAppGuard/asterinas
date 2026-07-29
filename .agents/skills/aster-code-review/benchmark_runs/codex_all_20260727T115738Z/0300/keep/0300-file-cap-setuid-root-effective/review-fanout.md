---
date: 2026-07-27
mode: diff
base: 043ef13c6
head: f5fc357bb
branch: HEAD
title: "Review of file capability execve handling"
---

# Summary

This change improves the shape of `execve()` capability handling by separating capability-set preparation from the no-return phase, but the refactor also removes the internal xattr bypasses that file-capability maintenance depended on.

The highest-risk issue is in `clear_file_capability_xattr()`: it now uses the DAC-checked `remove_xattr()` path. That can make ordinary writes/truncates fail after permissions change, and in `chown` paths it can leave a stale `security.capability` xattr after ownership metadata has already changed. The matching read-side change also makes executable-only files fail `execve()` when their file capabilities are read through a `MAY_READ`-checked path.

The other major correctness issue is that `exec_euid` is computed from inode metadata before the irreversible exec section, while `set_uid_from_elf()` later re-reads the same metadata. A single stable snapshot should drive both the capability calculation and the UID/GID application.

The maintainability comments are lower severity: the commit mixes parser/API cleanup with behavior changes, weakens the typed xattr-name invariant, duplicates file-capability parsing code, and leaves a helper name narrower than its actual responsibility.

## Maintainability

### `commit f5fc357bb message`

> ```diff
> [commit message]
> Refactor file capability execve handling
> 
> [changed paths]
> kernel/src/fs/vfs/fs_apis/xattr.rs
> kernel/src/process/credentials/file_capabilities.rs
> kernel/src/process/execve.rs
> ```

`atomic-commits` (minor): The commit subject says `Refactor file capability execve handling`, but the commit also changes the `Inode` xattr interface, changes `SECURITY_CAPABILITY_XATTR_NAME` from `XattrName<'static>` to `&str`, and rewrites the `FileCapabilities` parser with `VfsCapRevision` and `VfsCapFlags`. Those are separable parser/API cleanups from the `execve()` capability-set precomputation, so a future bisect or revert cannot isolate the actual `execve()` change.

**Fix.** Split the mechanical xattr/parser cleanup into an earlier refactor commit, then keep this commit focused on the `execve()` flow and the `ExecCapSets` handoff.

### `kernel/src/fs/vfs/fs_apis/xattr.rs` line 11

> ```diff
> -pub(crate) const SECURITY_CAPABILITY_XATTR_NAME: XattrName<'static> =
> -    XattrName::from_known_valid_full_name(XattrNamespace::Security, "security.capability");
> +pub const SECURITY_CAPABILITY_XATTR_NAME: &str = "security.capability";
> ...
> +    let xattr_name = XattrName::try_from_full_name(SECURITY_CAPABILITY_XATTR_NAME).unwrap();
> ```

`rust-type-invariants` (minor): Publishing `SECURITY_CAPABILITY_XATTR_NAME` as `&str` throws away the `XattrName` invariant that the old `from_known_valid_full_name` encoded. Internal callers now have to repeat `XattrName::try_from_full_name(...).unwrap()` at each use, so the `security.capability` name being known-valid is enforced by convention rather than by the type.

**Fix.** Keep a typed constant or a typed constructor for this kernel-owned name, for example `pub const SECURITY_CAPABILITY_XATTR_NAME: XattrName<'static> = XattrName::from_known_valid_full_name(...)`, and compare against `SECURITY_CAPABILITY_XATTR_NAME.full_name()` only at string boundaries such as syscall argument checks.

### `kernel/src/process/credentials/file_capabilities.rs` line 80

> ```diff
> +                let Ok(permitted) = CapSet::try_from_lo_hi(read_u32_le(raw_value, 1)?, 0) else {
> +                    return_errno_with_message!(
> +                        Errno::EINVAL,
> +                        "file capabilities contain unsupported capability bits"
> +                    );
> +                };
> +                let Ok(inheritable) = CapSet::try_from_lo_hi(read_u32_le(raw_value, 2)?, 0) else {
> ```

`dry` (minor): The `VfsCapRevision` arms repeat the same `CapSet::try_from_lo_hi(read_u32_le(...), read_u32_le(...))` conversion and identical `EINVAL` mapping five times. That duplicates the xattr word-layout knowledge and makes the parser harder to audit when another revision or error path changes.

**Fix.** Restore a helper such as `read_capset(raw_value, lo_word, hi_word)` or `build_capset(lo, hi)` that performs the `CapSet::try_from_lo_hi` conversion and common error mapping, leaving each `VfsCapRevision` arm to state only its layout.

### `kernel/src/process/execve.rs` line 327

> ```diff
>  fn apply_caps_from_exec(
>      process: &Process,
> -    credentials: Credentials<ReadWriteOp>,
> +    credentials: &Credentials<ReadWriteOp>,
>      elf_inode: &Arc<dyn Inode>,
> -    file_capabilities: Option<FileCapabilities>,
> +    capsets_for_exec: ExecCapSets,
>  ) -> Result<()> {
>      set_uid_from_elf(process, credentials, elf_inode)?;
>      set_gid_from_elf(process, credentials, elf_inode)?;
> ```

`accurate-names` (minor): `apply_caps_from_exec` sounds like it only applies capability sets, but the function also applies `setuid`, applies `setgid`, and clears `keep_capabilities`. Readers looking for the `execve()` credential mutation path have to inspect the body to learn that the helper is broader than its name.

**Fix.** Rename the helper to match its full responsibility, such as `apply_credentials_from_exec`, or split the `set_uid_from_elf`/`set_gid_from_elf` work from the `update_capsets_for_exec` work.

## Correctness

### `kernel/src/fs/vfs/fs_apis/xattr.rs` line 20

> ```diff
> 19     let xattr_name = XattrName::try_from_full_name(SECURITY_CAPABILITY_XATTR_NAME).unwrap();
> 20     match inode.remove_xattr(xattr_name) {
> 21         Ok(()) => Ok(()),
> ```

Incorrect permission check (major): `clear_file_capability_xattr()` now calls the ordinary `inode.remove_xattr()` path; on ext2 that path checks `Permission::MAY_WRITE` before removal. Write paths such as `InodeHandle::write()` are supposed to be governed by the already-open file descriptor's `Rights::WRITE`; if permissions are revoked after open, a later nonzero `write()` or `ftruncate()` can fail during capability cleanup before the actual file operation.

**Fix.** Shared with the other internal xattr bypass comments: restore kernel-internal xattr read/remove paths for `security.capability` that bypass DAC permission checks, and keep ordinary `get_xattr()`/`remove_xattr()` for user-requested xattr operations.

### `kernel/src/process/credentials/file_capabilities.rs` line 46

> ```diff
> 44         let xattr_name =
> 45             xattr::XattrName::try_from_full_name(xattr::SECURITY_CAPABILITY_XATTR_NAME).unwrap();
> 46         let value_len = match inode.get_xattr(xattr_name, &mut value_writer) {
> 47             Ok(value_len) => value_len,
> ```

Incorrect permission check (major): `FileCapabilities::read_from_inode()` now calls `inode.get_xattr()`; on ext2 that path checks `Permission::MAY_READ`. `execve()` only requires `MAY_EXEC` for the executable, so executing a mode like `0111` ext2 file with a `security.capability` xattr can fail with `EACCES` while reading capabilities even though the program is executable.

**Fix.** Shared with the other internal xattr bypass comments: restore kernel-internal xattr read/remove paths for `security.capability` that bypass DAC permission checks, and use the read side here instead of the syscall-facing `Inode::get_xattr()` method.

### `kernel/src/process/execve.rs` line 79

> ```diff
> 74     let exec_euid = if elf_file.mode()?.has_set_uid() {
> 75         elf_file.owner()?
> 76     } else {
> 77         credentials.euid()
> 78     };
> 79     let capsets_for_exec = credentials.prepare_capsets_for_exec(file_capabilities, exec_euid)?;
> ```

TOCTOU race (major): `exec_euid` is computed from `elf_file.mode()` and `elf_file.owner()` before the irreversible exec section, but `set_uid_from_elf()` later re-reads the inode metadata before applying `capsets_for_exec`. If another process changes the setuid bit or owner between these points, the UID actually applied at line `333` can differ from the UID used to calculate capabilities here; for example, clearing setuid-root after line `74` can still leave `capsets_for_exec` granting root-derived capabilities to a non-setuid exec.

**Fix.** Use one stable executable-credential snapshot for both capability calculation and UID/GID application. For example, compute the setuid decision and owner once before validation, store it with the prepared exec credentials, and have `apply_caps_from_exec()` apply that stored UID instead of re-reading `elf_inode.mode()`/`owner()`.

## Security

### `kernel/src/fs/vfs/fs_apis/xattr.rs` line 20

> ```diff
> -    match inode.remove_xattr_without_permission_check(SECURITY_CAPABILITY_XATTR_NAME) {
> +    let xattr_name = XattrName::try_from_full_name(SECURITY_CAPABILITY_XATTR_NAME).unwrap();
> +    match inode.remove_xattr(xattr_name) {
> ```

Incorrect permission boundary (critical): `clear_file_capability_xattr()` now calls the ordinary `inode.remove_xattr()` path; on ext2 that path rechecks DAC write permission. Callers such as `sys_fchown()` and `sys_fchownat()` mutate `uid`/`gid` before this clear; if the file is not writable under the resulting mode, the clear returns an error after the ownership change has already stuck, leaving `security.capability` on the changed file. For example, changing a capability-bearing `0500` executable to a different owner makes `MAY_WRITE` fail while the new owner can execute the file with the stale capabilities.

**Fix.** Shared with the other internal xattr bypass comments: restore kernel-internal xattr read/remove paths for `security.capability` that bypass DAC permission checks, and use the remove side from `clear_file_capability_xattr()` so privilege-invalidating metadata changes cannot leave stale file capabilities behind. Alternatively, make the ownership change and capability clear atomic or roll back the metadata change on clear failure.
