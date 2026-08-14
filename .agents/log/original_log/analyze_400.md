# log_0400 的 review 过程分析

## 结论

从 review 产物本身看，`log_0400.txt` 里有两次 review：

1. **combined review**：`--per-persona-context=no`，一个上下文同时审
   Maintainability、Correctness、Security。这个阶段只召回了 2/3 个 target
   defects，漏掉 `kernel/src/net/socket/unix/stream/connected.rs:202` 的
   zero-length `SOCK_SEQPACKET` receive assertion。
2. **fan-out review**：`--per-persona-context=yes`，每个 persona 独立审。
   从保存下来的 review 内容看，fan-out 已经召回 3/3 个 target defects。

所以，如果只讨论“review 方法为什么无法召回所有 target defect”，准确结论是：

- **真正的 review 漏报发生在 combined review 阶段**；
- **fan-out review 的最终报告没有漏掉 target defect**；
- `log_0400` 最后的 `recall 1/3 [fan-out]` 主要是后续评分环节的问题，不属于
  本文重点。本文只用它作为背景，不把它当作 review 产物本身的事实。

## 1. 本 case 的 target defects

日志保存的 expected defects 有 3 个：

| # | 位置 | target defect | review 侧结果 |
|---|---|---|---|
| 1 | `.github/workflows/test_x86.yml:84-100` | `matrix.release || true` 和 `matrix.enable_kvm || true` 会把显式 `false` 覆盖成 `true`，导致 debug/no-KVM CI job 实际没跑 | combined 已召回，fan-out 已召回 |
| 2 | `kernel/src/net/socket/unix/stream/connected.rs:202` | `debug_assert!(is_empty || read_tot_len != 0)` 会拒绝合法的零长度 `SOCK_SEQPACKET` receive，debug build 可 panic | **combined 漏报，fan-out 召回** |
| 3 | `kernel/src/process/signal/pause.rs:152-175` | `pause_timeout` 在注册 signal waker 后直接 `self.wait()`，没有先重查 pending signal，存在 lost-wakeup race | combined 已召回，fan-out 已召回 |

证据：

- expected defects 文件列出 3 个目标：`expected-defects.txt:3-13`。
- combined review headings 只有 `.github/workflows/test_x86.yml:84`、
  `.github/workflows/test_x86.yml:85`、`connected.rs:226`、`pause.rs:154`、
  `connected.rs:282`，没有 `connected.rs:202`。
- fan-out review headings 包含 `.github/workflows/test_x86.yml:84`、
  `.github/workflows/test_x86.yml:85`、`connected.rs:202`、`pause.rs:154`。
- 日志中 combined assembly 显示 `development=4, security=1`，对应 5 个 findings：
  `log_0400.txt:8531-8606`。
- 日志中 fan-out assembly 显示 `development=6`，并在 assembled report 里出现
  `connected.rs line 202`：`log_0400.txt:10364`、`log_0400.txt:10458-10466`。

## 2. 未召回的问题

### 未召回项：`connected.rs:202` 的 zero-length `SOCK_SEQPACKET` assertion

Target defect 是：

```rust
debug_assert!(is_empty || read_tot_len != 0);
```

这个 assertion 把“调用者接收 buffer 是否为空”和“协议是否允许零长度消息”混在一起。
对于 `SOCK_SEQPACKET`：

- 零长度 packet 是合法消息；
- 调用者的 receive buffer 可以是非空；
- 但合法空消息会让 `read_tot_len == 0`；
- 于是出现 `is_empty == false && read_tot_len == 0`；
- 原 assertion 在 debug build 下 panic。

这就是 expected defect #2 的核心语义。

combined review 没有报告这个问题。它报告了两个相邻但不同的问题：

- `connected.rs:226`：最大长度检查 `>= UNIX_STREAM_DEFAULT_BUF_SIZE` 的 off-by-one；
- `connected.rs:282`：零长度 send 不消耗 ring buffer，但仍追加 auxiliary metadata，
  可能导致无界资源占用。

这两个问题不能算召回 `connected.rs:202`，因为 target 要求的是 receive 端
`debug_assert!` 对合法零长度 seqpacket 的错误拒绝。

证据：

- combined assembled report 的 headings 没有 `connected.rs line 202`：
  `log_0400.txt:8919-8930`。
- combined review 的 final file 只有 79 行，也只列出 5 个 findings：
  `log_0400.txt:8933-8955`。
- combined review 的 socket 相关 findings 是 `line 226` 和 `line 282`：
  `log_0400.txt:8566-8576`、`log_0400.txt:8593-8606`。
- fan-out 的 development pass 明确补上 `line 202`：
  `log_0400.txt:10114` 中包含
  `"line":202` 和 `"A valid zero-length SOCK_SEQPACKET packet ... this debug_assert! panics"`。
- fan-out assembled report 也展示 `connected.rs line 202`：
  `log_0400.txt:10458-10466`。

## 3. review 方法存在的缺陷

### 3.1 combined persona 会稀释注意力

combined run 使用一个 prompt 同时覆盖多个 persona：

```text
maintainability development security
```

而 skill 文档本身也说明：

- `yes`: fan out one isolated agent per persona, best recall；
- `no`: one combined agent reviews all personas, cheaper, lower recall。

在本日志中，combined review 激活了 Maintainability、Development、Security，并构建了
一个 101467 字符的 combined prompt。

证据：

- `log_0400.txt:1732`：明确说正在构建 one combined pass，且 activated personas 是
  `maintainability`, `development`, `security`。
- `log_0400.txt:1734-1737`：combined prompt 大小为 `101467` 字符。
- `log_0400.txt:8531`：combined 产物只有
  `maintainability=0, development=4, security=1`。
- `log_0400.txt:8546-8606`：combined 只输出了 CI、line 226、pause race、
  line 282，没有 line 202。
- 对照 fan-out，`log_0400.txt:9946-9953` 显示每个 persona 单独构建 prompt，
  `development` prompt 只有 `53517` 字符；`log_0400.txt:10114` 显示
  development 独立 pass 找到了 line 202。

General 原因：

当一个 review pass 同时处理多个 persona、多个文件和多类缺陷时，模型会优先抓住
更显眼、更跨文件、更高层的模式：

- CI 表达式语义错误；
- signal wait race；
- socket metadata 资源增长；
- ring buffer 边界条件。

但 `connected.rs:202` 是一个局部 invariant bug，需要精确区分：

- receive buffer 是否为空；
- packet payload 是否为空；
- socket 类型是否允许空 packet；
- assertion 在 debug build 下是否可达。

这种局部协议 invariant 容易在 combined review 中被相邻问题淹没。

改进策略：

- recall-first 场景默认使用 fan-out，不把 combined 作为最终质量判断。
- combined 只能作为快速初筛；如果 combined 找不到全部高风险边界，必须升级 fan-out。
- 对 Development persona 单独运行时，应保留足够 token 和工具预算给协议语义、状态机、
  assertion 和边界条件。

### 3.2 review 缺少系统化的 assertion/invariant sweep

combined review 已经读到了 socket 代码，也发现了 zero-length seqpacket 的相关问题，
但没有检查最终 `debug_assert!` 是否仍对合法状态成立。

这说明当前 review 方法更像“发现若干显眼候选缺陷”，而不是系统地枚举和验证每个
关键 invariant。

证据：

- `log_0400.txt:8374`：combined reviewer 总结自己确认了
  “seqpacket implementation accepts zero-length sends while enqueueing metadata”，说明它已经
  注意到 zero-length seqpacket 路径。
- `log_0400.txt:8566-8576`：它检查了 `reader.sum_lens()` 的长度边界。
- `log_0400.txt:8593-8606`：它检查了 auxiliary metadata enqueue。
- 但 `log_0400.txt:8919-8930` 的 final heading list 没有 `line 202`。
- fan-out development pass 在同一份 review input 下找到了 line 202：
  `log_0400.txt:10114`。

General 原因：

很多内核 bug 不在复杂算法里，而在“局部 invariant 的条件写错”：

- `debug_assert!`/`assert!` 条件少了协议例外；
- 长度变量和状态变量语义相近但不同；
- “空 buffer”和“空消息”被混用；
- payload 长度和 message existence 被混用。

如果 review 只沿着高层数据流走，很容易发现资源泄漏或 race，却漏掉小而致命的
invariant。

改进策略：

- Development pass 加一个固定检查阶段：枚举所有 `assert!`、`debug_assert!`、
  `unwrap()`、`panic!`。
- 对每个 assertion 写出它依赖的语义变量，例如：
  “buffer empty”、“payload len”、“packet exists”、“socket type”。
- 对每个协议模式分别检查 assertion 是否成立：stream、seqpacket、zero-length、
  full buffer、partial read。
- 在 final review 前增加一项 checklist：如果报告里出现 zero-length 相关 finding，
  必须回查同一函数内所有依赖 length 的 invariant。

### 3.3 review 对“相邻问题”缺少去偏机制

combined review 报告了两个 socket 相关问题，但都不是 target 的 line 202：

- line 226 的 off-by-one；
- line 282 的 metadata/resource 问题。

这表明 reviewer 沿着 zero-length write/enqueue 方向深入了，但没有回到 receive 端
的 post-read assertion。

证据：

- `log_0400.txt:8574`：combined 认为最大消息检查拒绝 exact-capacity payload。
- `log_0400.txt:8604`：combined 认为零长度 send 可造成 metadata 无限增长。
- `log_0400.txt:8698-8700`：summary 也强调 metadata、CI、pause 和 exact maximum
  packet size，没有提到 line 202 的 debug assertion。
- fan-out development pass 的顺序显示，独立 Correctness review 同时输出 line 263
  和 line 202：`log_0400.txt:10114`。

General 原因：

当模型已经找到一个看似充分的缺陷后，容易停止继续挖同一段代码的其他 failure mode。
在 review benchmark 里，这会造成“找到相关问题但没有命中 target defect”的漏报。
尤其是：

- 同一函数同时有多个缺陷；
- send path 和 receive path 共享变量或队列；
- 一个 zero-length case 同时影响 readiness、metadata、assertion。

改进策略：

- 对每个已发现 finding 的附近代码做 second-pass：同一个函数、同一个状态变量、
  同一个协议分支是否还有独立 failure mode。
- 不因为已经找到一个 socket zero-length 问题就停止；要区分 send、receive、
  poll/readiness、metadata、assertion 五类影响。
- 输出候选 findings 前，检查每个候选是否覆盖不同 root cause 或不同触发点；
  对未覆盖的触发点继续扫描。

### 3.4 verification 只能防 false positive，不能补 recall hole

combined review 在 verification 后没有删除任何 finding，但也没有新增 line 202。
这符合当前 skill 设计：verification 的目标是 refute 已有 comments，而不是发现
未提出的问题。

证据：

- `log_0400.txt:8683`：combined 阶段说
  “Verification did not refute any”，然后直接进入 consolidation 和 summary。
- `log_0400.txt:8686-8700`：之后只是编辑 summary 和 shared fix。
- `log_0400.txt:8919-8930`：最终 headings 仍没有 `connected.rs line 202`。

General 原因：

如果 pipeline 中“生成 findings”和“验证 findings”是单向流程，那么一个真实缺陷
只要没在生成阶段出现，后续 verification 不会把它补回来。review 的 recall 依赖
初始 pass 的覆盖范围。

改进策略：

- 在 verification 前增加 completeness review，不是验证已有 comments，而是检查
  “是否还有未覆盖的 assertion、边界、wake-up sequence、user-visible config”。
- 或者要求每个 persona pass 输出简短 coverage notes：
  已检查哪些协议模式、哪些 assertions、哪些 wait/waker 顺序。
- 如果 coverage notes 里没有提到某类高风险结构，例如 `debug_assert!` 或
  zero-length message，应触发补充 pass。

### 3.5 执行 fallback 改变了标准 review 流程

combined review 阶段本来要通过 nested `codex exec` 执行 pass，但 nested pass
启动失败，主 agent 改为直接完成 review。

证据：

- `log_0400.txt:1739`：nested `codex exec` 启动失败，错误是
  `Unable to spawn codex-linux-sandbox`、`No viable candidates found in PATH`。
- `log_0400.txt:1741`：主 agent 表示如果没有等价 sub-agent，就直接完成 review。
- `log_0400.txt:9362` 和 `log_0400.txt:9481`：最终说明
  “nested codex exec pass could not start ... completed and verified the combined review directly”。

General 原因：

review 方法依赖“隔离 pass + 稳定 prompt + JSON fragments”。当执行环境迫使主 agent
fallback 到直接审查时，会产生几个风险：

- prompt contract 和 selective exposure 可能不完全一致；
- 主 agent 同时承担 orchestration、代码阅读、finding 生成、验证和整理；
- review 过程更容易受上下文历史和手工编辑影响；
- 缺少真正独立的 persona 判断。

本 case 中 fan-out 后来仍能找全 target，所以 fallback 不是最终 fan-out 漏报原因；
但它解释了 combined 阶段为什么更像一次人工综合审查，而不是标准化 pass。

改进策略：

- 如果 nested pass 无法启动，应把该 run 标记为 degraded review，不与标准流程结果混用。
- fallback review 也应强制执行同样的 persona checklist 和 completeness sweep。
- 对 benchmark 来说，最好让 review harness fail closed，避免 fallback 产物被误认为
  标准 combined-pass 质量。

## 4. 为什么 fan-out 能补回漏报

fan-out review 做了几件 combined 没做到的事：

1. 每个 persona 单独 prompt，Development 不再和 Maintainability/Security 争上下文。
2. Development pass 明确输出 6 个 candidate defects，其中包括多个 zero-length
   seqpacket/pause edge cases。
3. line 202 的 assertion 被直接写入 development fragment。
4. assemble 后 final report 保留了 line 202 comment。

证据：

- `log_0400.txt:9944-9964`：fan-out 准备四个独立 persona prompts 并并发运行。
- `log_0400.txt:10108`：日志说 Correctness pass 找到 6 个 candidate defects，
  包括 “several zero-length seqpacket/pause edge cases”。
- `log_0400.txt:10114`：development JSON 里有 `connected.rs`, `line:202`,
  `Reachable panic`。
- `log_0400.txt:10360-10364`：四个 persona passes 全部完成，assemble 显示
  `development=6`。
- `log_0400.txt:10458-10466`：final report 展示 line 202 finding。
- `log_0400.txt:13668-13672`：最终 heading list 同时包含 CI、line 202、pause。

General 原因：

fan-out 提高 recall 的关键不是“更多 comments”，而是让每个 persona 的认知任务
更窄。Development pass 可以集中处理：

- 协议边界；
- wait/waker race；
- assertion 可达性；
- zero-length message；
- readiness 和 buffer state。

这些正是 combined review 容易被其他 persona 任务稀释的内容。

改进策略：

- 保持 `per_persona_context=yes` 作为 recall benchmark 的默认和推荐模式。
- 对 files mode 中包含多个 subsystem 的 case，禁止只依赖 combined review 的结果。
- 如果为了成本先跑 combined，必须把 fan-out 作为 miss 或低覆盖时的强制升级路径。

## 5. 每个未召回问题的 general 原因和改进策略

本日志中，从 review 角度只有一个 target defect 在 combined 阶段未召回。

### `connected.rs:202` zero-length `SOCK_SEQPACKET` assertion

General 原因：

- 这是局部协议 invariant，不是显眼的数据流 bug。
- 它需要区分 receive buffer 是否为空、payload length 是否为 0、message 是否存在、
  socket type 是否允许空消息。
- combined review 已经找到相邻的 zero-length send/metadata 问题，容易产生“这一段已经
  看过了”的偏差。
- verification 只确认已有 comments，不补扫没提出的 assertion。

证据：

- target 明确要求 line 202：`expected-defects.txt:7-9`。
- combined review 缺少 line 202：`log_0400.txt:8919-8930`。
- combined 只报告相邻 socket 问题：`log_0400.txt:8566-8576`、
  `log_0400.txt:8593-8606`。
- fan-out development 独立 pass 能找到 line 202：
  `log_0400.txt:10114`、`log_0400.txt:10458-10466`。

改进策略：

- 在 Development review 中加入 assertion sweep。
- 对协议代码加入 zero-length/empty/full/partial 的固定边界矩阵。
- 对同一函数内已发现的 zero-length finding 做 nearby second-pass。
- 将 combined review 的结果视为候选，不作为 recall-first 的最终结果。
- verification 前加入 completeness pass，而不是只验证已有 comments。

## 6. Review 方法的 general 改进清单

1. **默认 fan-out，不默认 combined。**
   combined 可以省成本，但对 recall-first 不可靠。日志里 line 202 正是 combined 漏掉、
   fan-out 找回的例子。

2. **给 Development persona 加结构化边界清单。**
   对内核代码固定检查 assertion、长度比较、zero-length、full-capacity、partial
   read/write、wait/waker 顺序。

3. **对相邻 finding 做二次扫描。**
   如果发现一个 zero-length 问题，不要停止；继续检查同一状态是否影响 receive、
   send、poll/readiness、metadata、assertion。

4. **把 verification 和 completeness 分开。**
   verification 是防误报；completeness 是防漏报。当前日志显示 verification 没有
   refute finding，但也没有补回 line 202。

5. **degraded fallback 要显式标记。**
   nested pass 启动失败后由主 agent 直接 review，这种结果不应和标准 pass 结果等价。
   如果允许 fallback，必须强制执行相同 checklist。

6. **要求 pass 输出简短 coverage notes。**
   例如 Development pass 应说明是否检查过 assertions、zero-length packets、
   wait/waker race、CI boolean defaults。缺少 coverage notes 时触发补充 review。

## 最终总结

从 review 角度看，`log_0400` 暴露的主要问题是：

- combined review 漏掉了 `connected.rs:202` 的 legal zero-length
  `SOCK_SEQPACKET` receive assertion；
- 漏报原因不是完全没看 socket 代码，而是看到了相邻 zero-length/metadata/boundary
  问题，却没有系统检查 receive 端 assertion；
- 这反映出 combined persona 注意力稀释、缺少 assertion/invariant sweep、
  缺少 nearby second-pass、verification 不能补 recall hole 等 review 方法缺陷；
- fan-out review 通过独立 Development pass 找回了这个缺陷，说明 persona 隔离和更窄
  的 correctness focus 对 recall 有明显帮助。

因此，general 的改进方向是：**保持 fan-out 作为 recall-first 默认；为 Development
review 增加结构化 invariant/boundary/zero-length/waker checklist；在验证前增加
completeness pass；对 degraded fallback 做显式标记和额外检查。**
