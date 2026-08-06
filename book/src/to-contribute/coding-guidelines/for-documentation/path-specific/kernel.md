# `kernel/`

Guidelines that apply only to code under `kernel/`.

### Keep the Linux Compatibility docs current (`linux-compat-docs`) {#linux-compat-docs}

When a change under `kernel/` adds or enhances a user-visible API — a system call or a kernel parameter —
update the [Linux Compatibility](../../../../kernel/linux-compatibility/) section in the same PR,
so the documented coverage keeps matching the code.

- For a **system call**:
  update the matching [Syscall Flag Coverage](../../../../kernel/linux-compatibility/syscall-flag-coverage/) page
  and its [SCML](../../../../kernel/linux-compatibility/syscall-flag-coverage/system-call-matching-language.md) (`.scml`) coverage file
  to reflect the newly supported flags, arguments, and behaviors.
- For a **kernel parameter**:
  update the [Kernel Parameters](../../../../kernel/linux-compatibility/kernel-parameters.md) page.

#### Steps

1. Review `kernel/` changes for new or changed system calls, syscall flags, syscall argument semantics, return values, errors, and kernel parameters.
2. For syscall changes, check the matching Syscall Flag Coverage page and `.scml` file for updated flags, arguments, and behavior.
3. For kernel parameter changes, check the Kernel Parameters page for the new or changed name, value format, default, and effect.
4. Require documentation updates in the same PR whenever user-visible Linux compatibility behavior changes.
