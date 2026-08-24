- problem_id: 0411-ext2-super-block-defects
  commit: 34ebccb2e9cb984ae928a7289cb5829e6f335253
  remote: https://github.com/asterinas/asterinas
  source: >
    PR-derived from https://github.com/asterinas/asterinas/pull/2675. The PR
    fixes three ext2 superblock defects in snapshot
    `34ebccb2e9cb984ae928a7289cb5829e6f335253`: the in-memory `SuperBlock`
    did not retain all fields from `RawSuperBlock`, `FsState` was modeled as a
    single enum even though ext2 uses bit flags, and `log_block_size` /
    `log_frag_size` were recalculated incorrectly when writing the superblock
    back. The reviewed snapshot is before fixing commits
    `d6f0b8708eecf0a1b36e62b09cd3de444e021547`,
    `92508c504c4f9ebbbc192b099441f774c647cd9d`, and
    `6cdc784c5b3d1b581c72e9d2d769f7f605c3e3b2`, so the targets are leak-free.
  review_mode:
    files:
      - kernel/src/fs/ext2/super_block.rs
  defects:
    - target:
        kind: file
        path: kernel/src/fs/ext2/super_block.rs
        lines: "531-536"
      persona: development
      grounding: preserve every on-disk superblock field on writeback
      severity: major
      desc: >
        `RawSuperBlock::from(&SuperBlock)` writes the known layout fields and
        then fills the remaining raw superblock fields from `Default`. Because
        `SuperBlock` never stored fields such as `min_rev_level`,
        `algorithm_usage_bitmap`, journal metadata, hash seed, mount options,
        `first_meta_bg`, and the reserved tail, any superblock read and later
        written back silently zeroes that on-disk information.
      fix: >
        Make `SuperBlock` retain the full `RawSuperBlock` information and copy
        those fields back explicitly instead of using `..Default::default()`.
      expectation: >
        A reviewer should flag that converting through `SuperBlock` must be a
        lossless read-modify-write path for all on-disk superblock fields,
        including currently unused and reserved ext2/ext3 metadata.

    - target:
        kind: file
        path: kernel/src/fs/ext2/super_block.rs
        lines: "378-386"
      persona: development
      grounding: model ext2 fs state as bit flags
      severity: major
      desc: >
        `FsState` is declared as a `TryFromInt` enum with mutually exclusive
        values, so a valid ext2 state containing both clean and error bits
        (`0x0003`) is rejected as invalid. The special `Corrupted = 117` enum
        value also treats the field as a single status code rather than the
        bitmask used by the on-disk format.
      fix: >
        Replace the enum with `bitflags!` over `u16`, defining the valid
        `VALID` and `ERROR` bits, parse with `FsState::from_bits`, and write
        back with `state.bits()`.
      expectation: >
        A reviewer should identify that ext2 `s_state` is a bit-field and
        require combined valid bits to round-trip instead of being rejected by
        enum conversion.

    - target:
        kind: file
        path: kernel/src/fs/ext2/super_block.rs
        lines: "507-508"
      persona: development
      grounding: compute ext2 log sizes from 1024-byte units
      severity: major
      desc: >
        The writeback calculation stores `log_block_size` and `log_frag_size`
        as `sb.block_size >> 11` and `sb.frag_size >> 11`. Ext2 defines these
        fields as the exponent `N` in `size = 1024 << N`; shifting by 11 only
        happens to return `2` for a 4096-byte size and gives wrong values for
        other valid sizes such as 1024 or 2048 bytes.
      fix: >
        Compute the exponent as
        `(size / SUPER_BLOCK_SIZE).trailing_zeros()` for both block and
        fragment sizes, matching the read-side formula
        `SUPER_BLOCK_SIZE << log_*_size`.
      expectation: >
        A reviewer should verify the inverse relationship between ext2's
        on-disk `log_*_size` fields and the in-memory byte sizes, and reject a
        right-shift formula that is not the inverse of the read path.
