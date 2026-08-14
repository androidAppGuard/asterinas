# log_0403 的 review 过程分析

## 结论

`log_0403.txt` 对应 benchmark case：

```text
0403-pr-podman-small-issues
```

review 模式是 files mode，目标文件为：

```text
kernel/src/syscall/madvise.rs
kernel/src/syscall/capget.rs
kernel/src/syscall/open.rs
```

本 case 有 3 个 target defects。最终 fan-out review 的 recall 是：

```text
1/3
```

证据：

- 日志中的 expected defects 明确列出 3 个目标问题：`log_0403.txt:7019-7029`。
- produced review 的 summary 说明它主要关注 `sys_madvise()`，并明确说没有在
  `kernel/src/syscall/open.rs` 找到 concrete issue：`log_0403.txt:7041-7045`。
- 最终 harness 结果是 `0403-pr-podman-small-issues recall 1/3 [fan-out]`：
  `log_0403.txt:7225-7228`。

从 review 内容看，召回的是第 1 个 `madvise` reachable `todo!()` panic。
漏召回的是：

1. `capget` 的 Linux version-query 协议：unsupported version 时应写回 supported version，
   且 query 场景允许 null data pointer；
2. `openat` 空 pathname 应在 syscall 边界显式返回 `ENOENT`，不能交给通用 path
   resolver 处理。

本次失败不是 grader 侧的问题，而是 review 过程把注意力集中在 `madvise` 的多个
明显风险和 `capget` 的另一个相邻 ABI 问题上，没有完整建模 `capget`/`openat`
这两个 syscall 的 Linux ABI contract。

## 1. Target defects 和 review 结果

| # | target defect | 位置 | review 结果 |
|---|---|---|---|
| 1 | `MadviseBehavior` 声明了 `MADV_NOHUGEPAGE`，但 `sys_madvise` match 没有处理它，会落入 `_ => todo!()`；Podman 调用 `MADV_NOHUGEPAGE` 会触发 kernel panic | `kernel/src/syscall/madvise.rs:35-50` | 已召回 |
| 2 | `sys_capget` 对 unsupported capability version 直接返回 `EINVAL`，没有把 `LINUX_CAPABILITY_VERSION_3` 写回 header；同时无条件写 `cap_user_data_addr`，不允许 version-query 场景的 null data pointer | `kernel/src/syscall/capget.rs:20-49` | 未召回 |
| 3 | `sys_openat` 对空 pathname 没有在 syscall 边界返回 `ENOENT`；`openat` 没有 `AT_EMPTY_PATH` 语义，空路径不应被通用 resolver 当成 cwd/fd 路径处理 | `kernel/src/syscall/open.rs:21-40` | 未召回 |

证据：

- expected defect #1：`log_0403.txt:7019-7021`。
- expected defect #2：`log_0403.txt:7023-7025`。
- expected defect #3：`log_0403.txt:7027-7029`。
- review 对 `madvise` line 48 输出 reachable panic finding：
  `log_0403.txt:7135-7148`，并且 security persona 又重复指出 user-controlled
  behavior 会落入 `todo!()`：`log_0403.txt:7187-7202`。
- review 对 `capget` 的 finding 是 version 3 只写一个 `cap_user_data_t`、丢失高 32 位：
  `log_0403.txt:7083-7101`。这不是 target #2 的 version-query/null-data 语义。
- review summary 明确说没有找到 `open.rs` concrete issue：`log_0403.txt:7043-7045`。

## 2. 未召回问题一：capget version-query 和 null-data 语义

### Target 要求

`sys_capget` 的目标缺陷是 Linux capability probing 协议没有实现完整：

```rust
if cap_user_header.version != LINUX_CAPABILITY_VERSION_3 {
    return_errno_with_message!(Errno::EINVAL, "not supported (capability version is not 3)");
};
...
user_space.write_val(cap_user_data_addr, &result)?;
```

源码证据：

- 读取 userspace header：`log_0403.txt:1525-1532`。
- unsupported version 直接返回 `EINVAL`：`log_0403.txt:1534-1536`。
- 无条件写 `cap_user_data_addr`：`log_0403.txt:1562-1563`。

expected defect 要求 reviewer 同时指出两件事：

1. unsupported version 调用应通过 header pointer 写回 supported version；
2. version-query 场景允许 `data == NULL`，不能无条件 dereference/reject data pointer。

证据：`log_0403.txt:7023-7025`。

### Review 实际说了什么

review 的 `capget` finding 是：

```text
capget() accepts LINUX_CAPABILITY_VERSION_3, but writes only one cap_user_data_t.
Version 3 exposes 64-bit capability sets as two 32-bit records...
```

证据：`log_0403.txt:7083-7101`。

这确实是一个相邻 ABI 问题，但它没有提到：

- unsupported version 时要写回 supported version；
- null data pointer 在 version-query 场景应返回成功；
- Podman capability probing 依赖这个 version negotiation。

review 的 verification 也显示它后续验证的是高 32 位 capability 被截断：
`log_0403.txt:4880-4883`。这进一步说明 review 路径已经从 target 的
version-query protocol 偏到了另一个数据宽度问题。

### Review 过程缺陷

**缺陷 A：只审查局部数据布局，没有审查 syscall 的协议型状态机。**

`capget` 不是单纯的结构体读写函数，它有一个 userspace probing protocol：
用户可以先传 unsupported version 或 null data 来查询 ABI version。review 只看到
`LINUX_CAPABILITY_VERSION_3`、`cap_user_data_t` 和 64-bit capability split，
于是把问题归纳为“写了一个 record、丢高位”。它没有追踪：

1. header version 输入不支持时应如何修改 header 输出；
2. data pointer 是否在所有路径都必须有效；
3. query-only 调用和 ordinary query 调用的不同语义。

**缺陷 B：把“相邻正确问题”当成了该文件的主要风险，导致 target 语义被覆盖。**

review summary 只总结 `capget` 的高位 capability 丢失：
`log_0403.txt:7043-7045`。这说明在 `capget` 上 review 已经停止于第一个看起来
合理的 ABI mismatch，没有继续检查 Linux man-page 级别的完整 contract。

### General 原因

这类漏召回的一般原因是：review 过度依赖代码表面结构和注释中的局部暗示，
缺少“syscall ABI checklist”。当代码里出现 version 字段、nullable userspace pointer、
probe/query 这类信号时，review 需要主动切换到协议审查，而不是只看最终数据
struct 是否写完整。

### 改进策略

- 对所有 syscall review 增加 ABI protocol checklist：
  `unsupported version/flags`、`output parameter writeback`、`nullable pointer`、
  `query-only mode`、`partial success/error code`。
- 当函数同时有 input header 和 output data pointer 时，强制枚举路径：
  valid version + valid data、unsupported version + data null、unsupported version + data
  non-null、valid version + data null。
- 对“发现的相邻问题”做一次 target drift 检查：这个 finding 是否覆盖了用户可见 ABI
  contract，还是只覆盖了内部结构体表示。

## 3. 未召回问题二：openat 空 pathname

### Target 要求

`sys_openat` 读取 pathname 后直接构造 `FsPath` 并进入 resolver：

```rust
let path = ctx.user_space().read_cstring(path_addr, MAX_FILENAME_LEN)?;
...
let fs_path = FsPath::new(dirfd, path.as_ref())?;
...
.open(&fs_path, flags, mask_mode)
```

源码证据：

- `sys_openat` 读取 path：`log_0403.txt:1580-1588`。
- `FsPath::new(dirfd, path.as_ref())` 后直接 open：`log_0403.txt:1593-1605`。

`FsPath::new` 对空相对路径的语义不是 `ENOENT`：

- `dirfd >= 0 && path.is_empty()` 时构造 `FsPathInner::Fd(dirfd)`：
  `log_0403.txt:2095-2101`。
- `dirfd == AT_FDCWD && path.is_empty()` 时构造 `FsPathInner::Cwd`：
  `log_0403.txt:2103-2108`。
- 只有 `TryFrom<&str> for FsPath` 对空字符串返回 `ENOENT`：
  `log_0403.txt:2119-2125`，但 `sys_openat` 走的是 `FsPath::new`，不是这个
  `TryFrom` 路径。

expected defect 要求 reviewer 指出：`openat` 没有 `AT_EMPTY_PATH`，空 pathname
必须在 syscall 边界显式返回 `ENOENT`。证据：`log_0403.txt:7027-7029`。

### Review 实际说了什么

review 没有输出任何 `open.rs` finding。summary 反而明确说：

```text
I did not find a concrete issue in kernel/src/syscall/open.rs.
```

证据：`log_0403.txt:7043-7045`。

### Review 过程缺陷

**缺陷 A：把 path resolver 的通用行为误认为 syscall 边界行为已经正确。**

`FsPath::new` 在通用路径层面允许 empty path 映射到 fd/cwd，这可能对某些内部 API
是有意义的。但 `openat` 的 Linux syscall contract 不允许空 pathname。review 没有把
“通用 helper 的可接受输入”与“syscall 的合法输入”区分开。

**缺陷 B：过早宣布某个目标文件没有问题。**

review summary 在最终产物中明确排除了 `open.rs`：`log_0403.txt:7045`。但 expected
defect 正好在 `open.rs`。这说明 review 没有建立每个目标文件的边界条件覆盖表，
而是在找到 `madvise` 的多个高风险点后，对 `open.rs` 做了较浅的负结论。

### General 原因

这类漏召回的一般原因是：review 在遇到 wrapper syscall 时，只追踪“是否调用了通用
resolver/helper”，没有检查该 syscall 是否需要在调用 helper 之前施加更严格的
Linux-specific precondition。通用 helper 的行为越宽松，syscall wrapper 越需要审查
输入边界。

### 改进策略

- 对每个 syscall wrapper 建立 boundary-condition checklist：empty string、null pointer、
  invalid fd、unsupported flags、特殊 flags 是否存在。
- 当 syscall 直接调用共享 path helper 时，要求 reviewer 明确回答：
  helper 的空路径/相对路径/fd 路径语义是否等同于该 syscall 的 Linux 语义。
- 避免在 summary 中写“没有 concrete issue”前缺少证据。若要排除某文件，应列出已经
  验证过的关键边界条件。

## 4. 已召回问题：madvise reachable todo panic

review 对 `madvise` 的召回基本覆盖 target #1：

- expected defect 指出 `MADV_NOHUGEPAGE` 会落入 `_ => todo!()`：
  `log_0403.txt:7019-7021`。
- review 指出 `_ => todo!()` 对用户传入的合法 advice 值可达，会 panic：
  `log_0403.txt:7135-7148`。
- security finding 也指出 user-controlled `behavior` 会触发 panic：
  `log_0403.txt:7187-7202`。

不足之处是，review 的例子主要列 `MADV_RANDOM`、`MADV_REMOVE`、
`MADV_PAGEOUT`，没有把 target 中的 `MADV_NOHUGEPAGE` 作为主例。但它已经覆盖了
“declared valid enum value reaches `todo!()`”这一核心问题，所以 final recall 计为 1/3。

## 5. 现有 review 方法的 general 缺陷总结

### 5.1 对明显 panic/DoS 问题敏感，但对协议细节不够敏感

证据：

- review 输出了大量 `madvise` panic、allocation、`MADV_FREE` 语义 findings：
  `log_0403.txt:7103-7202`。
- 对 `capget` 则停留在 capability 高 32 位丢失：
  `log_0403.txt:7083-7101`。
- 没有覆盖 `capget` version negotiation/null-data query：
  expected 在 `log_0403.txt:7023-7025`，produced review 无对应 finding。

改进策略：

- syscall review 不能只按“panic/overflow/allocation”扫描；必须有 Linux ABI
  protocol pass。
- 对有 version、flags、nullable output pointer 的 syscall，必须写出 input/output
  state table。

### 5.2 缺少 target-file 覆盖 ledger

证据：

- review summary 说没有 `open.rs` concrete issue：`log_0403.txt:7043-7045`。
- 但 expected defect #3 正在 `open.rs`：`log_0403.txt:7027-7029`。

改进策略：

- files mode 下对每个输入文件至少记录一个“已检查的关键语义/边界条件”。
- 如果某文件没有 finding，应记录 negative evidence，例如“empty path checked,
  returns ENOENT at syscall boundary”。没有这种证据时，不应轻易排除。

### 5.3 对相邻问题缺少“是否命中 target 语义”的二次校准

证据：

- `capget` review finding 是真实问题，但不是 expected #2：
  `log_0403.txt:7083-7101` vs `log_0403.txt:7023-7025`。
- verification 也继续围绕高 32 位 capability：`log_0403.txt:4880-4883`。

改进策略：

- 每个 finding 输出前加一句 internal check：
  “这个问题的用户可见失败场景是什么？是否覆盖该 API 最核心的 Linux contract？”
- 对协议类 API，不满足 query/negotiation/error-code 语义的 finding，不能替代协议
  finding。

## 6. 总结

`log_0403` 的漏召回核心不是模型没有读到文件，而是 review 优先级和抽象层次错位：

1. `madvise` 中的 `todo!()`、大分配、`MADV_FREE` 行为都很显眼，吸走了主要注意力；
2. `capget` 被当成 capability 数据布局问题审查，没有审查 version-query/null-data
   protocol；
3. `openat` 被当成普通 path resolver 调用，没有在 syscall 边界检查 empty pathname
   Linux 语义；
4. review 缺少每个 syscall 的 ABI checklist 和每个目标文件的覆盖 ledger。

对应的 general 改进方向是：在 syscall review 中引入独立的 ABI contract pass，
对 versioned ABI、nullable output pointer、empty pathname、unsupported flags 等
Linux 边界语义逐项验证；同时对每个目标文件保留覆盖证据，避免因为其他文件中出现
更多显眼问题而过早排除低行数、小 wrapper 中的 defect。
