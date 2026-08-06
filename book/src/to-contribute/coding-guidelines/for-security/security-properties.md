# Security Properties

### Validate at boundaries, trust internally (`validate-at-boundaries`) {#validate-at-boundaries}

Designate certain interfaces as validation boundaries.
In Asterinas, syscall entry points
are the primary boundary:
all user-supplied data
(pointers, file descriptors, sizes, flags, strings)
must be validated at the syscall boundary.
Once validated, internal kernel functions
may trust these values without re-validation.

#### Steps

1. Identify every value entering from userspace, devices, boot data, filesystems, network packets, or other untrusted boundaries.
2. Check boundary validation for pointers, lengths, flags, enum values, fds, strings, alignment, and ranges.
3. Require internal APIs to accept validated types or clearly documented trusted values rather than repeatedly accepting raw untrusted inputs.
4. Verify that validation and use are not separated by a race or mutation that can invalidate the checked property.

See also:
PR [#2806](https://github.com/asterinas/asterinas/pull/2806).
