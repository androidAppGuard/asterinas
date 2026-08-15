# log_0403: 为什么查了资料仍未召回 `openat` empty pathname target

分析对象：

```text
log/log_link_domainknowledge/log_0403.txt
```

目标问题：

```text
reject empty pathname for openat
```

## 结论

agent **确实查询了外部资料**，也确实对 `openat` 做了额外分析；但它最终没有召回
`openat` empty pathname target。它召回的是另一个相邻 pathname 问题：

```text
to_string_lossy() rewrites invalid UTF-8 pathname bytes
```

而不是：

```text
openat("", ...) should return ENOENT before generic path resolution
```

关键证据：

- expected target 明确要求 empty pathname / `ENOENT` / `AT_EMPTY_PATH` 语义：
  `log_0403.txt:9199-9201`。
- produced review 的 `openat` finding 是 non-UTF-8 pathname 被 `to_string_lossy()` 改写：
  `log_0403.txt:9424-9434`。
- summary 也只提到 `sys_openat` rewrites non-UTF-8 pathname bytes：
  `log_0403.txt:9214-9216`。
- 最终 recall 是 `2/3`，说明仍有一个 target 未召回：
  `log_0403.txt:9504-9511`。

因此，本 target 的准确判断是：

```text
未召回。
```

## 1. agent 的实际分析过程

### 1.1 它先被 contract 要求查询 authoritative sources

log 中的 pass prompt 包含新增的 source-check contract：

- review 外部 API/ABI/语言/硬件 contract 时要先 consult authoritative source：
  `log_0403.txt:370-373`。
- preferred primary sources 包括 Linux man pages、Linux source、POSIX、hardware manuals、
  Rust Reference：`log_0403.txt:374-382`。
- 要识别 semantic rule、invariant、error behavior，不能只依赖记忆、本地注释或实现意图：
  `log_0403.txt:383-389`。

这说明 agent 在流程上已经被要求查资料。

### 1.2 它确实查询了 Linux man pages

与 `openat`/pathname 相关的查询包括：

- `path_resolution(7)`：`log_0403.txt:8264-8265`。
- `pathname(7)`：`log_0403.txt:8266-8267`。

最终 review 写出：

```text
Authoritative references checked: capget(2), madvise(2), pathname(7).
```

证据：

- `log_0403.txt:9081-9086`。
- `log_0403.txt:9163-9167`。

注意：最终记录的 authoritative references 里有 `pathname(7)`，但没有明确记录
`openat(2)` 或 `open(2)`。这对本 target 很重要，因为 empty pathname 是否允许属于
`openat` syscall contract，不只是一般 pathname 字节表示问题。

### 1.3 它明确说要对 `openat` 做最后一轮检查

在分析 `capget` 后，agent 写道：

```text
I’m doing one last pass over `openat` for reachable panics or syscall contract mismatches.
```

证据：`log_0403.txt:7400-7402`。

随后它执行了多组本地搜索：

- 搜索 `read_cstring`、`MAX_FILENAME_LEN`、`to_string_lossy()`、`FsPath::new`：
  `log_0403.txt:7403-7408`。
- 搜索结果中明确看到 `sys_openat` 的关键路径：
  `kernel/src/syscall/open.rs:21` 读取 path，`open.rs:29` 调用 `FsPath::new`：
  `log_0403.txt:7437-7439`。

这说明 agent 看到了 target 所在的关键调用链：

```text
read_cstring -> to_string_lossy -> FsPath::new -> resolver.open
```

### 1.4 它读到了 empty pathname 在 `FsPath::new` 中的特殊处理

agent 后续读取了 `kernel/src/fs/fs_resolver.rs` 相关代码。日志显示：

- `FsPath::new` 创建 `FsPath`：`log_0403.txt:7881-7884`。
- 如果 `dirfd >= 0 && path.is_empty()`，返回 `FsPathInner::Fd(dirfd)`：
  `log_0403.txt:7888-7894`。
- 如果 `dirfd == AT_FDCWD && path.is_empty()`，返回 `FsPathInner::Cwd`：
  `log_0403.txt:7896-7900`。

这正是 target 的本地代码证据：empty pathname 没有在 `sys_openat` 边界返回
`ENOENT`，而是进入 generic path handling，变成 fd/cwd 语义。

agent 还读到了一个对照证据：

- `FsPath::try_from` 对 empty string 返回 `ENOENT`：
  `log_0403.txt:7912-7919`。

这说明仓库里其实存在“empty path should be ENOENT”的局部语义，但 `sys_openat` 没走
这个路径。

agent 还读到了另一个 syscall 的显式 empty-path 检查：

- `sys_unlinkat` 在 `path_name.is_empty()` 时返回 `ENOENT`：
  `log_0403.txt:7852-7859`。

这个对照本来可以帮助发现 `sys_openat` 缺少同类边界检查。

### 1.5 但最终输出偏到了 non-UTF-8 pathname

最终 development pass 输出的 `openat` finding 是：

```text
`to_string_lossy()` rewrites invalid UTF-8 pathname bytes before lookup.
Linux pathnames are C strings of non-null bytes...
```

证据：

- JSON fragment：`log_0403.txt:8357-8364`。
- produced review 正文：`log_0403.txt:9424-9434`。

summary 同样只总结这个问题：

```text
sys_openat also rewrites non-UTF-8 pathname bytes through `to_string_lossy()`
```

证据：`log_0403.txt:9214-9216`。

因此，agent 的实际路径是：

```text
查了 pathname/path_resolution 资料
读了 sys_openat 和 FsPath::new
发现了 to_string_lossy 的 pathname byte-semantics 问题
把 openat finding 聚焦在 non-UTF-8 pathname
没有输出 empty pathname / ENOENT finding
```

## 2. 为什么查了资料仍然未召回

### 原因一：查到的是 pathname 通用资料，但没有把问题落到 `openat(2)` 的 empty-path contract

证据：

- agent 查询了 `path_resolution(7)` 和 `pathname(7)`：
  `log_0403.txt:8264-8267`。
- 最终记录 checked references 只有 `capget(2)`、`madvise(2)`、`pathname(7)`：
  `log_0403.txt:9081-9086`、`log_0403.txt:9163-9167`。
- produced `openat` finding 也引用的是 `pathname(7)`，用于说明 Linux pathname 是
  non-null byte string：`log_0403.txt:9432-9434`。

分析：

`pathname(7)` 能帮助发现“路径名是字节串，不能 `to_string_lossy()`”这个问题，
但 target 需要的是更具体的 syscall 语义：

```text
openat("", ...) is invalid and should return ENOENT;
openat has no AT_EMPTY_PATH option.
```

agent 没有把 authoritative-source check 精确绑定到 `openat(2)` 的 empty pathname
规则，因此外部资料查询被用于另一个 pathname defect，而不是 target defect。

### 原因二：agent 看到了 empty-path 代码证据，但没有把 generic helper 语义和 syscall boundary 语义区分开

证据：

- `sys_openat` 直接调用 `FsPath::new(dirfd, path.as_ref())`：
  `log_0403.txt:7437-7439`。
- `FsPath::new` 中 empty path 被解释成 `FsPathInner::Fd(dirfd)`：
  `log_0403.txt:7888-7894`。
- `FsPath::new` 中 `AT_FDCWD + empty` 被解释成 `FsPathInner::Cwd`：
  `log_0403.txt:7896-7900`。
- `TryFrom<&str> for FsPath` 反而会对 empty path 返回 `ENOENT`：
  `log_0403.txt:7912-7919`。
- `sys_unlinkat` 也显式对 empty path 返回 `ENOENT`：
  `log_0403.txt:7852-7859`。

分析：

这些证据足以构造 target finding：

```text
sys_openat should reject empty path before FsPath::new,
because FsPath::new treats empty path as fd/cwd.
```

但 agent 没有完成这一步。它可能把 `FsPath::new` 的 empty-path 行为当作通用 resolver
设计的一部分，没有问：

```text
这个通用 helper 对 empty path 的宽松解释，是否适合 openat syscall boundary？
```

这就是 wrapper syscall review 中常见的问题：看到 helper 能处理输入，就误以为 syscall
语义也正确。

### 原因三：candidate filtering 让它偏向“直接可见的局部错误”，弱化了跨层 contract mismatch

证据：

agent 在输出 final JSON 前写道：

```text
I’ve isolated several concrete runtime defects in the syscall implementations.
I’m filtering out broader design limitations unless the reviewed lines directly create
an externally visible wrong result or reachable panic.
```

证据：`log_0403.txt:8262-8263`。

分析：

`openat` empty pathname defect 是一个跨层问题：

```text
sys_openat boundary missing check
  -> FsPath::new generic empty-path behavior
  -> resolver opens cwd/fd-like target
  -> Linux openat contract should be ENOENT
```

它不如 `to_string_lossy()` 那样在单行上显得“直接错误”。`to_string_lossy()` 更容易被
agent 归类为 reviewed line directly creates wrong result，因为 line 28 直接改写 bytes。

因此 candidate filtering 可能导致：

- 保留 `to_string_lossy()` finding；
- 丢掉或没有形成 empty pathname finding。

### 原因四：相邻 pathname defect 抢占了 `openat` 的唯一 finding 槽位

证据：

- final JSON 中 `open.rs` 只有 `to_string_lossy()` finding：
  `log_0403.txt:8357-8364`。
- produced review 中 `open.rs` section 也只有该 finding：
  `log_0403.txt:9424-9434`。
- summary 对 `sys_openat` 只提 non-UTF-8 pathname：
  `log_0403.txt:9214-9216`。

分析：

agent 查了 pathname 资料后，确实发现了一个真实 Linux pathname defect。
但这个相邻 defect 吸收了 `openat` 的注意力。它没有继续做 second pass：

```text
除了 byte-string 语义，openat 的特殊输入还有哪些？
empty string?
AT_EMPTY_PATH?
trailing slash?
O_PATH?
```

结果是：找到了一个更显眼、更容易用 `pathname(7)` 支撑的问题，但漏掉 benchmark target。

### 原因五：没有把“empty pathname”作为 syscall boundary checklist 项

证据：

- expected target 明确要求 empty pathname 在 `sys_openat` boundary 返回 `ENOENT`：
  `log_0403.txt:9199-9201`。
- agent 搜索/阅读了 `FsPath::new` 相关代码，但最终输出没有 `empty`、`ENOENT`、
  `AT_EMPTY_PATH` 相关 finding；最终 `openat` finding 是 invalid UTF-8：
  `log_0403.txt:9424-9434`。
- final recall 仍为 `2/3`：`log_0403.txt:9504-9511`。

分析：

这说明 primary-source 查询本身不足够。review pass 还需要 syscall boundary checklist。
对 path syscalls 至少应强制检查：

```text
empty pathname
NULL pointer
non-UTF-8 / arbitrary bytes
trailing slash
AT_EMPTY_PATH or absence of it
dirfd handling
O_PATH / O_NOFOLLOW / O_DIRECTORY interactions
```

本 case 中 agent 做了“arbitrary bytes/non-UTF-8”检查，但漏了“empty pathname”和
“AT_EMPTY_PATH absence”。

## 3. 未召回原因总结

### 3.1 直接原因

agent 最终输出的 `openat` finding 是：

```text
to_string_lossy() rewrites invalid UTF-8 pathname bytes
```

证据：`log_0403.txt:9424-9434`。

target 需要的是：

```text
empty pathname reaches generic path resolution;
sys_openat should return ENOENT explicitly before resolution.
```

证据：`log_0403.txt:9199-9201`。

两者是相邻但不同的 Linux pathname defect，所以 target 未召回。

### 3.2 根本原因

1. **source 查询目标不够精确。**
   agent 查了 `pathname(7)`，但没有把 `openat(2)` empty pathname/`AT_EMPTY_PATH`
   作为必须确认的 rule。证据：`log_0403.txt:8264-8267`、
   `log_0403.txt:9081-9086`。

2. **跨层语义连接失败。**
   agent 看到了 `sys_openat -> FsPath::new`，也看到了 `FsPath::new` 对 empty path
   返回 `Fd/Cwd`，但没有判断这违反 `openat` syscall boundary。证据：
   `log_0403.txt:7437-7439`、`log_0403.txt:7888-7900`。

3. **局部直接错误优先于协议边界错误。**
   agent 明确说会过滤 broader design limitations，保留直接外部可见错误；最终保留了
   `to_string_lossy()`。证据：`log_0403.txt:8262-8263`、
   `log_0403.txt:8357-8364`。

4. **缺少 path-syscall boundary checklist。**
   `empty pathname` 没有成为强制检查项；否则 `FsPath::new` 的 `Fd/Cwd` 分支和
   `sys_unlinkat` 的 `ENOENT` 对照应该足以触发 finding。证据：
   `log_0403.txt:7852-7859`、`log_0403.txt:7888-7900`、
   `log_0403.txt:7912-7919`。

## 4. 改进策略

### 4.1 对 syscall wrapper 增加 boundary checklist

对所有 syscall wrapper，尤其是 path syscalls，review pass 应显式枚举：

```text
empty string
NULL pointer
unsupported flags
special flags that opt into otherwise-invalid inputs
helper behavior vs syscall-specific behavior
```

对于 `openat`，必须有一项：

```text
Does this syscall allow an empty pathname?
If yes, which flag enables it?
If no, where does it return ENOENT before generic path resolution?
```

### 4.2 source 查询要绑定具体语义问题

不要只写：

```text
check pathname(7)
```

而要写：

```text
check open/openat empty pathname behavior and whether AT_EMPTY_PATH applies
```

这样查询会落到 target rule，而不是泛化成 pathname byte-string rule。

### 4.3 对 helper 调用做“contract narrowing”检查

当 syscall wrapper 调用通用 helper 时，review 应强制回答：

```text
helper accepts more inputs than this syscall permits?
helper rejects inputs this syscall permits?
helper maps special values to internal meanings that are illegal at syscall boundary?
```

本 case 中答案是：

```text
FsPath::new accepts empty string and maps it to Fd/Cwd,
but openat does not permit empty pathname.
```

### 4.4 对相邻 finding 做 target-drift 检查

当同一代码段已经产出一个 finding 时，review pass 需要再问：

```text
This finding is real, but did I cover all externally specified edge cases
on this syscall boundary?
```

否则容易出现本 case 的情况：`to_string_lossy()` 是真实问题，但它不是 target 的
empty pathname 问题。

## 5. 最终判断

`log_0403` 中，agent **查了资料**，包括 `path_resolution(7)`、`pathname(7)`，并最终记录
checked authoritative references；它也读到了 `sys_openat` 和 `FsPath::new` 的 empty-path
处理代码。但它没有把这些证据组合成：

```text
openat empty pathname must return ENOENT before FsPath::new
```

最终 review 只报告：

```text
to_string_lossy() rewrites invalid UTF-8 pathname bytes
```

所以 `reject empty pathname for openat` target **未召回**。
