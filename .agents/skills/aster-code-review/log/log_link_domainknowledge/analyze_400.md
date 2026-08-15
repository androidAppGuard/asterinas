# log_0400 primary-source 查询与 target 召回分析

分析对象：

```text
log/log_link_domainknowledge/log_0400.txt
```

对应 case：

```text
0400-ci-false-seqpacket-zero-pause-race
```

## 结论

| 检查项 | 结论 | 关键证据 |
|---|---|---|
| agent 在 review 期间是否会查询 Prefer primary sources | 会。prompt 中注入了 primary-source contract，实际执行中也出现了 Linux man page 相关 web search。 | contract: `log_0400.txt:360-379`；实际 search: `log_0400.txt:3176-3177`、`log_0400.txt:17595-17602` |
| 是否召回 `Allow legal zero-length SOCK_SEQPACKET messages` target | 召回。produced review 明确指出合法 zero-length `SOCK_SEQPACKET` 会触发 line 202 的 `debug_assert!`，并要求 invariant 基于 `is_seqpacket`。 | expected: `log_0400.txt:17967-17969`；review: `log_0400.txt:18159-18171` |

最终 recall：

```text
0400-ci-false-seqpacket-zero-pause-race recall 2/3 [fan-out]
```

证据：`log_0400.txt:18269-18276`。

## 1. 是否查询 Prefer primary sources

### 1.1 prompt 中明确要求查询权威来源

本轮 log 中的 pass prompt 已经包含新增的 primary-source contract：

```text
When reviewing code that implements, wraps, emulates, or depends on an externally
specified API, ABI, language rule, or hardware contract,
consult the authoritative source needed to understand that contract before
deciding whether the code is correct.
Prefer primary sources:
Linux man pages ...
Linux source ...
POSIX ...
hardware vendor manuals ...
Rust Reference ...
```

证据：

- `log_0400.txt:360-363`：要求 review 外部 API/ABI/语言/硬件 contract 时先 consult authoritative source。
- `log_0400.txt:364-372`：列出 preferred primary sources，包括 Linux man pages、Linux source、POSIX、hardware manuals、Rust Reference。
- `log_0400.txt:373-379`：要求识别 semantic rule/invariant/error behavior，不能只依赖记忆、本地注释或实现意图。

这说明 agent 在 review pass 的 prompt 层面已经被要求查询 primary sources。

### 1.2 实际 review 期间出现了 primary-source 查询

实际 log 中有 Linux man page web search：

- `log_0400.txt:3176-3177`：

```text
web search:
web search: https://man7.org/linux/man-pages/man7/unix.7.html
```

后续 verification/consolidation 阶段也出现了与本 case 相关的外部查询：

- `log_0400.txt:17595-17602`：

```text
web search: GitHub Actions expressions operators || false true documentation
web search: GitHub Actions contexts reference matrix context composite actions matrix available contexts
web search: man7 send zero-length datagram SOCK_SEQPACKET zero-length message
web search: man7 sigprocmask SIGKILL SIGSTOP cannot be blocked
```

其中 `man7 send zero-length datagram SOCK_SEQPACKET zero-length message` 和
`man7 sigprocmask SIGKILL SIGSTOP cannot be blocked` 都属于 Linux man page 方向的
primary-source 查询。

produced review 中也引用了 Linux man pages：

- `log_0400.txt:18212-18214`：security finding 引用 `sigprocmask(2)` 和 `signal(7)` 说明 `SIGKILL`/`SIGSTOP` 不能被 block。

### 1.3 判断

结论：**会查询 primary sources。**

不过要注意一个细节：对 zero-length `SOCK_SEQPACKET` 这个 target，log 显示 agent
主要先通过本地代码路径确认问题，再在后续阶段搜索 `man7 send zero-length...`：

- 本地确认 zero-length 代码路径：`log_0400.txt:17480-17481`。
- 外部搜索发生在后续：`log_0400.txt:17595-17602`。

因此更准确的说法是：

```text
agent 确实会查 primary sources；
但在 0400 中，它不是对每一个 target 都先查外部资料再开始推理。
zero-length SOCK_SEQPACKET 问题主要由本地代码推理发现，之后再进入外部资料/验证阶段。
```

## 2. `Allow legal zero-length SOCK_SEQPACKET messages` 是否召回

### 2.1 target 要求

expected defect #2 是：

```text
Allow legal zero-length SOCK_SEQPACKET messages
```

目标问题：

- `Connected::try_read` 允许 `SOCK_SEQPACKET` 的 zero-length read；
- 但最终 invariant 是 `debug_assert!(is_empty || read_tot_len != 0)`；
- `is_empty` 表示 caller 的 receive buffer 是否为空，不表示 socket type 是否允许 zero-length packet；
- 合法 empty `SOCK_SEQPACKET` message 会在 `is_empty == false && read_tot_len == 0` 时触发 debug panic；
- review 必须要求 invariant 基于 `is_seqpacket` 或等价 protocol-aware 条件。

证据：`log_0400.txt:17967-17969`。

### 2.2 produced review 是否满足 MATCH IF

produced review 在 `kernel/src/net/socket/unix/stream/connected.rs` line 202 输出：

```text
Reachable panic (major): A valid zero-length `SOCK_SEQPACKET` receive reaches
this `debug_assert!`: `send(..., len = 0)` queues an auxiliary range with
`start == end`, `try_read()` pops it with `read_tot_len == 0`, and a non-empty
receive buffer makes `is_empty` false.
```

并且 fix 明确要求：

```text
make this invariant allow the queued zero-length packet case,
for example `debug_assert!(is_empty || is_seqpacket || read_tot_len != 0);`
```

证据：`log_0400.txt:18159-18171`。

这完全覆盖 expected defect 的 MATCH IF：

- 指出 assertion rejects legal zero-length `SOCK_SEQPACKET` receives；
- 指出触发条件是 `is_empty == false` 且 `read_tot_len == 0`；
- 要求 invariant 包含 `is_seqpacket` 或 protocol-aware condition。

### 2.3 相关补充 finding

produced review 还额外指出 zero-length `SOCK_SEQPACKET` readiness 问题：

- `check_io_events()` 只看 byte ring 是否非空；
- zero-length message 只在 `peer_end.all_aux` 中，没有 bytes；
- blocked `recvmsg()`/`poll()` 可能睡眠；
- fix 要求 readiness state 表示 zero-length sequenced packet。

证据：`log_0400.txt:18173-18183`。

这个 finding 不是 target #2 的必要条件，但说明 review 对同一 zero-length
`SOCK_SEQPACKET` 问题族有进一步分析。

### 2.4 判断

结论：**召回。**

虽然本 case 最终只有 `2/3` recall，漏掉的是 3 个 target 中的另一个问题；
`Allow legal zero-length SOCK_SEQPACKET messages` 本身已经被 produced review 明确命中。

## 3. 总结

`log_0400` 中可以确认两点：

1. agent 的 pass prompt 已包含 primary-source 查询 contract，并且实际 review 期间出现了
   Linux man page 相关查询；
2. `Allow legal zero-length SOCK_SEQPACKET messages` target 被准确召回，review comment
   直接锚定 line 202 的 `debug_assert!`，描述了合法 zero-length `SOCK_SEQPACKET`
   的触发路径，并给出 `is_seqpacket` 条件修复方向。
