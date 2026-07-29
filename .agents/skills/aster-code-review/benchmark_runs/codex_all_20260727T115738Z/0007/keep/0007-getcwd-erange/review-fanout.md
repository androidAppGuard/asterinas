---
date: 2026-07-27
mode: diff
base: 171adc36a
head: 6678565c8
branch: HEAD
---

# Summary

The change is small and localized, but it breaks the main `getcwd` short-buffer contract: callers now get success with truncated data instead of `ERANGE`. That contradicts the Linux/POSIX behavior, breaks the existing `getcwd_small_buffer_returns_erange` regression test, and makes the "fully covered" Linux-compatibility documentation inaccurate unless this behavior is intentionally reclassified.

Top issues:
- Major: restore the `ERANGE` path when the full NUL-terminated CWD does not fit in the user buffer.
- Major: if the changed behavior were intended, update the syscall coverage docs; otherwise the docs remain correct only after reverting the behavioral change.
- Minor: rewrite the commit subject in verb-first imperative style.

## Maintainability

### `commit 6678565c8 message`

> ```diff
> [commit message]
> fs/getcwd: fill the user buffer up to its length
> ```

`imperative-subject` (minor): The subject starts with the scope prefix `fs/getcwd:` instead of a verb-first imperative subject, and it names `getcwd` without backticks. This does not follow the commit-message convention for Asterinas changes.

**Fix.** Rewrite the subject as a verb-first imperative sentence, for example: `Change getcwd to fill caller buffers partially`.

## Correctness

### `kernel/src/syscall/getcwd.rs` line 30

> ```diff
>  let cwd = CString::new(abs_path)?;
>  let bytes = cwd.as_bytes_with_nul();
> -    if bytes.len() > len {
> -        return_errno_with_message!(Errno::ERANGE, "the CWD buffer is too small");
> -    }
> -    ctx.user_space().write_bytes(buf, bytes)?;
> +    let write_len = len.min(bytes.len());
> +    ctx.user_space().write_bytes(buf, &bytes[..write_len])?;
>  
> -    Ok(SyscallReturn::Return(bytes.len() as _))
> +    Ok(SyscallReturn::Return(write_len as _))
> ```

Incorrect syscall semantics (major): When `len` is smaller than `bytes.len()`, `sys_getcwd()` now copies a truncated path and returns success. A concrete existing case is `getcwd(small, 1)`: it writes only the first byte of `"/\0"` and returns `1`, so callers do not get the required `ERANGE` failure and may observe a non-terminated or incomplete path.

**Fix.** Restore the too-small-buffer check before writing, and return `ERANGE` instead of partial success:

```rust
if bytes.len() > len {
    return_errno_with_message!(Errno::ERANGE, "the CWD buffer is too small");
}
ctx.user_space().write_bytes(buf, bytes)?;
Ok(SyscallReturn::Return(bytes.len() as _))
```

## Security

### `kernel/src/syscall/getcwd.rs` line 30

> ```diff
> -    let write_len = len.min(bytes.len());
> -    ctx.user_space().write_bytes(buf, &bytes[..write_len])?;
> +    if bytes.len() > len {
> +        return_errno_with_message!(Errno::ERANGE, "the CWD buffer is too small");
> +    }
> +    ctx.user_space().write_bytes(buf, bytes)?;
>  
> -    Ok(SyscallReturn::Return(write_len as _))
> +    Ok(SyscallReturn::Return(bytes.len() as _))
> ```

`validate-at-boundaries` (major): When the caller passes a `len` smaller than `bytes.len()` (including `0`), `len.min(bytes.len())` silently accepts the invalid user-supplied size and returns success after copying a truncated, potentially non-NUL-terminated pathname. The syscall boundary should reject an undersized `getcwd` buffer with `ERANGE` instead of hiding the contract violation.

**Fix.** Shared with the Correctness finding: restore the boundary check before copying and only return success when the full C string fits in `buf`.

## Documentation

### `kernel/src/syscall/getcwd.rs` line 30

> ```diff
> -    if bytes.len() > len {
> -        return_errno_with_message!(Errno::ERANGE, "the CWD buffer is too small");
> -    }
> -    ctx.user_space().write_bytes(buf, bytes)?;
> +    let write_len = len.min(bytes.len());
> +    ctx.user_space().write_bytes(buf, &bytes[..write_len])?;
> ```

`linux-compat-docs` (major): This changes the user-visible `getcwd` syscall contract for short buffers from returning `ERANGE` to writing a truncated pathname and returning `write_len`, but the Linux Compatibility syscall coverage artifacts were not updated. `getcwd` is still listed as fully covered in `book/src/kernel/linux-compatibility/README.md` and `book/src/kernel/linux-compatibility/syscall-flag-coverage/file-and-directory-operations/fully_covered.scml`, so the docs no longer track the implemented behavior.

**Fix.** Shared with the Correctness and Security findings: keep the existing fully-covered documentation claim by restoring `ERANGE`, or update the matching Syscall Flag Coverage page and `.scml` entry for `getcwd` in the same change if the short-buffer behavior is intentionally changed.
