# log_0403 primary-source 查询与 target 召回分析

分析对象：

```text
log/log_link_domainknowledge/log_0403.txt
```

对应 case：

```text
0403-madvise-nohugepage-capget-query-openat-empty
```

用户要求重点判断两个 target：

1. `match capget version negotiation and null-data semantics`
2. `reject empty pathname for openat`

## 结论

| 检查项 | 结论 | 关键证据 |
|---|---|---|
| agent 在 review 期间是否会查询 Prefer primary sources | 会。prompt 中注入了 primary-source contract，实际执行中多次查询 Linux man pages 和 Linux source/Elixir。 | contract: `log_0403.txt:370-389`；实际 search: `log_0403.txt:2064-2067`、`log_0403.txt:2536-2543`、`log_0403.txt:8267-8273` |
| `match capget version negotiation and null-data semantics` 是否召回 | 严格按 target 的 MATCH IF：**未完整召回**。review 抓到了 unsupported version 要写回 supported version，但没有抓到 null data pointer 的 query-success 语义；fix 还写成 unsupported version 后返回 `EINVAL`。 | expected: `log_0403.txt:9195-9197`；review: `log_0403.txt:9310-9323`；docs comment: `log_0403.txt:9486-9488` |
| `reject empty pathname for openat` 是否召回 | 未召回。review 报的是 `to_string_lossy()` 导致非 UTF-8 pathname 被改写，不是 empty pathname 应返回 `ENOENT`。 | expected: `log_0403.txt:9199-9201`；produced review openat finding: `log_0403.txt:9424-9434` |

最终 harness recall：

```text
0403-madvise-nohugepage-capget-query-openat-empty recall 2/3 [fan-out]
```

证据：`log_0403.txt:9504-9511`。

注意：从 final `2/3` 看，grader 很可能把 `capget` target 计为召回，
因为 review 抓到了 version writeback/probing 的一半；但从 target 自己的
MATCH IF 看，它要求同时指出 supported version writeback 和 null data pointer
query 语义。因此本文把它判为 **未完整召回/部分召回**，而不是完整召回。

## 1. 是否查询 Prefer primary sources

### 1.1 prompt 中明确要求查询权威来源

本轮 log 的 pass prompt 包含 primary-source contract：

- `log_0403.txt:370-373`：要求 review 外部 API/ABI/语言/硬件 contract 时先 consult authoritative source。
- `log_0403.txt:374-382`：列出 preferred primary sources，包括 Linux man pages、Linux source、POSIX、hardware manuals、Rust Reference。
- `log_0403.txt:383-389`：要求识别 semantic rule/invariant/error behavior，不能只依赖记忆、本地注释或实现意图。

### 1.2 实际 review 中有 Linux man page / Linux source 查询

0403 中实际出现多次 primary-source 查询。

早期 maintainability pass 查询了 `capget(2)`：

- `log_0403.txt:2064-2067`：

```text
web search:
web search: https://man7.org/linux/man-pages/man2/capget.2.html
I’ve confirmed one external-comment concern against the current `man7.org` `capget(2)` page...
```

后续又查询了 `madvise(2)`、`capget(2)` 和 Linux source/Elixir：

- `log_0403.txt:2536-2543`：

```text
web search: https://man7.org/linux/man-pages/man2/madvise.2.html
web search: https://man7.org/linux/man-pages/man2/capget.2.html
web search: https://elixir.bootlin.com/linux/latest/source/include/uapi/asm-generic/mman-common.h
web search: site:elixir.bootlin.com linux include/uapi/asm-generic/mman-common.h MADV_FREE
```

对于 pathname/openat 相关行为，也查询了 Linux man page：

- `log_0403.txt:8267-8273`：

```text
web search: https://man7.org/linux/man-pages/man7/pathname.7.html
web search: https://man7.org/linux/man-pages/man2/capget.2.html
web search: https://man7.org/linux/man-pages/man2/madvise.2.html
```

最终 review 中也留下了 “authoritative references checked” 记录：

- `log_0403.txt:9086`：

```text
Authoritative references checked: capget(2), madvise(2), pathname(7).
```

- `log_0403.txt:9167`：同样记录 checked references。

### 1.3 判断

结论：**会查询 primary sources。**

0403 不只是 prompt 中要求查询；实际 log 中明确出现了：

- Linux man pages：`capget(2)`、`madvise(2)`、`pathname(7)`；
- Linux source/Elixir：`include/uapi/asm-generic/mman-common.h`。

但查询 primary sources 并不等于一定能召回所有 target。下面两个 target 就说明了这一点：

- `capget` 查询了 man page，但没有完整提取 null-data query 语义；
- `openat` 查询了 pathname/open 相关资料，但 review 输出偏到了非 UTF-8 pathname，而不是 empty pathname。

## 2. `match capget version negotiation and null-data semantics`

### 2.1 target 要求

expected defect #2 要求 reviewer 同时指出两个缺陷：

1. unsupported capability version 时，必须把 supported version 写回 userspace header；
2. null data pointer 在 version-query 场景中允许成功，不能无条件 dereference/reject。

证据：

- `log_0403.txt:9195-9196`：说明 `sys_capget` unsupported version 直接 `EINVAL`，没有写回 `LINUX_CAPABILITY_VERSION_3`，且无条件写 `cap_user_data_addr`，因此 null data pointer 不能成功。
- `log_0403.txt:9197`：MATCH IF 明确要求 reviewer flag **both missing parts**：supported version writeback 和 null data pointer query 语义。

### 2.2 review 抓到了 version writeback

produced review 在 `kernel/src/syscall/capget.rs` line 20 输出 correctness finding：

```text
When `hdrp->version` is unsupported, Linux `capget()` must fail with `EINVAL`
and write the kernel's preferred capability version back to `hdrp->version`;
this returns `EINVAL` without updating the user header...
```

证据：`log_0403.txt:9310-9323`。

这说明 review 抓到了 target 的第一半：

```text
unsupported version -> write supported version back to header
```

summary 也提到 `sys_capget` 的 version probing 不匹配 Linux ABI：

- `log_0403.txt:9216`。

documentation finding 也说 Linux `capget(2)` documents version probing：

- `log_0403.txt:9486-9488`。

### 2.3 review 没有抓到 null-data semantics

target 要求的第二半是：

```text
null data pointer must not be dereferenced or rejected when the call is only
querying the ABI version.
```

证据：`log_0403.txt:9196-9197`。

produced review 中没有对应内容：

- correctness finding 只说 unsupported version 要写回 header，并要求之后返回 `EINVAL`：
  `log_0403.txt:9321-9323`。
- 该 fix 没有提到 `cap_user_data_addr == 0`、`datap == NULL`、query-only success、
  或避免无条件 `write_val(cap_user_data_addr, ...)`。
- documentation finding 只说 version probing、`datap[0]`/`datap[1]`、target pid、
  upper capability words：`log_0403.txt:9486-9488`，也没有说 null data pointer 可用于
  version query。

更关键的是，review 的 fix 写成：

```text
write it back to cap_user_header_addr, and then return EINVAL on unsupported versions.
```

证据：`log_0403.txt:9323`。

这和 target 中 “null data pointer version-query case should return success” 并不等价。
如果 userspace 用 unsupported version + null data pointer 做 version query，review 的
fix 仍然没有说明应返回 success。

### 2.4 判断

结论：**严格意义上未完整召回；只能算部分召回。**

理由：

- 已召回：unsupported version 要写回 supported version；
- 未召回：null data pointer 在 version-query case 中允许成功；
- target 的 MATCH IF 要求 “both missing parts”，所以从语义完整性看不能判为完整召回。

但需要记录一个 harness 层面的现象：

- 最终 recall 是 `2/3`：`log_0403.txt:9508-9511`。
- 本 case 的 openat empty pathname 明显未召回；
- 因此 harness 很可能把 capget finding 按 version writeback/probing 计入了召回。

这说明：

```text
benchmark final recall 可能把 capget target 计为 caught；
但从人工严格审查 target 文本看，review 漏掉了 null-data semantics。
```

## 3. `reject empty pathname for openat`

### 3.1 target 要求

expected defect #3 要求 reviewer 指出：

- `sys_openat` 读取 pathname 后直接传给 `FsPath::new` 和 resolver；
- empty pathname 没有在 syscall boundary 返回 `ENOENT`；
- `openat` 没有 `AT_EMPTY_PATH` 选项，所以 empty pathname 不合法；
- review 应要求 `sys_openat` 在 resolution 前显式返回 `ENOENT`。

证据：

- `log_0403.txt:9199-9201`。

### 3.2 review 实际输出的是另一个 openat 问题

produced review 中唯一明确的 `open.rs` correctness finding 是：

```text
Incorrect pathname handling (major): `to_string_lossy()` rewrites invalid UTF-8
pathname bytes before lookup...
```

证据：`log_0403.txt:9424-9434`。

这个 finding 的核心是：

```text
Linux pathnames are byte strings；不能用 to_string_lossy 改写非 UTF-8 bytes。
```

它没有提到：

- empty pathname；
- `ENOENT`；
- `AT_EMPTY_PATH`；
- 在 `FsPath::new` 前显式拒绝 empty path。

summary 也只说：

```text
sys_openat also rewrites non-UTF-8 pathname bytes through to_string_lossy()
```

证据：`log_0403.txt:9216`。

### 3.3 判断

结论：**未召回。**

虽然 agent 查询了 `pathname(7)` 并输出了一个真实的 pathname 兼容性问题，
但它不是 target 要求的 empty pathname / `ENOENT` 问题。

换句话说：

```text
review 找到了 openat 的相邻 Linux pathname defect，
但没有召回 reject empty pathname for openat。
```

## 4. 总结

`log_0403` 的关键结论是：

1. agent 确实会查询 primary sources。log 中有明确的 `man7.org` 和 `elixir.bootlin.com`
   查询记录，并且最终 review 多处引用 Linux man pages。
2. `capget` target 被 **部分召回**：review 抓到了 unsupported version 时要写回
   supported version，但没有抓到 null data pointer version-query success 语义。
3. `openat` empty pathname target **未召回**：review 报的是 non-UTF-8 pathname 被
   `to_string_lossy()` 改写，不是 empty pathname 应返回 `ENOENT`。

这说明新增 primary-source contract 改善了 agent 对 Linux ABI 的关注度，
但仍不能保证它从权威文档中提取完整的 target 语义；尤其是一个 target 包含多个必要条件时，
review 可能只抓到其中一个条件。
