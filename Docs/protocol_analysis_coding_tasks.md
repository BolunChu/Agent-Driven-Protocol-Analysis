# Coding Agent 开发任务拆解

## 一、项目目标

实现一个面向通用网络协议的协议分析系统原型，当前以文本协议为主，支持 FTP、SMTP、RTSP、HTTP 等协议，融合多智能体、function calling、证据绑定、在线探测和 WebUI 可视化。

当前阶段的主目标进一步收敛为：

- 让一个基于 function calling 的 agent 系统能够较完整地分析文本协议
- 以“agent 调用工具主导分析”为核心目标，规则解析仅作为 fallback 与安全护栏
- 课程作业阶段不追求完整复现 ChatAFL / ProtocolGPT，也不以 SOTA 或完整 ProFuzzBench 覆盖为目标
- 以“对若干文本协议稳定抽取 message types、粗粒度状态、部分转移与证据链，并能通过 probe 做少量修正”作为主要阶段性衡量标准
- ProFuzzBench 当前主要作为 seeds / traces / 真实协议样本来源，而不是最终竞赛式 benchmark
- 所有关键改动都需要同步体现在 WebUI 的分析进度与结果展示中
- 所有架构和实现变化都必须同步更新到文档

### 当前目标更新（2026-04-26）

- 继续坚持 agent-first：正常路径优先由 agent tool calls 产出模型，规则层仅做 fallback 与护栏
- 评估报告必须可观测来源：每次迭代都输出 agent/fallback 贡献分布，避免“看起来跑通但无法判断主导路径”
- 当前重点是把 FTP、SMTP、RTSP、HTTP 四个文本协议做成稳定、可比较、可展示的课程作业闭环
- 近期不继续扩展高难协议；如需扩展，优先选择 SIP、POP3 等较简单文本协议，而非 TLS / SSH / DTLS 一类复杂协议
- 在保持 message_types 清洁和状态语义稳定的前提下，提升 Trace 转移覆盖稳定性，减少不同轮次波动

### 已记录建议（优先执行）

- 为四个已接入协议建立统一的课程作业验收口径：message types、states、transitions、evidence、probe、agent/fallback 占比都要可导出、可比较
- 为 Trace 增加最小覆盖护栏：当 LLM 输出转移数低于阈值时，按高价值命令集定向补齐
- 将覆盖阈值和补齐命令集下沉到 ProtocolAdapter 配置，避免 service 层硬编码
- 建立连续回归门槛（建议 3-5 轮）：关注 trace fallback 率、transition 下界、message_types 清洁度

项目目标不是重写现有 ChatAFL 或 ProtocolGPT，也不是做完整 fuzzing 复现，而是实现一个新的课程作业级通用协议分析平台，重点在于：

- 多源输入协议知识抽取
- 多智能体协作分析
- 证据绑定的协议模型构建
- 在线探测驱动的模型修正
- WebUI 展示状态机与证据链
- WebUI 展示 pipeline 运行进度、artifact 摘要、建议动作与当前项目结果

---

## 当前实施进展（2026-04-26，更新至多协议闭环第一阶段）

当前仓库已经从 FTP-only 原型演进到多协议文本协议闭环第一阶段。当前最成熟的是 FTP，已经具备较完整的 agent-first 分析链路；SMTP、RTSP、HTTP 也已完成专属 adapter、parser、probe executor、种子、trace、文档摘要和启动脚本，能够跑通端到端流程。

当前阶段的项目定位是课程作业原型：重点证明 agent 系统能够对多个文本协议稳定抽取一部分有意义的协议结构，而不是追求完整恢复复杂状态机，也不是去做完整 ProFuzzBench 全协议 benchmark。围绕“从 FTP-only 演进到多协议文本协议分析平台”的后续实施蓝图，已单独整理到：`Docs/multi_protocol_framework_blueprint.md`。

### 已完成能力

- ProFuzzBench FTP seed 数据已接入，目录为 `data/traces/profuzzbench/`
- 本地 FTP 探测服务启动脚本已提供：`scripts/start_ftp_server.py`
- 完整分析流程脚本已提供：`scripts/run_full_analysis.py`
- LLM 接入层已实现：`backend/app/core/llm_client.py`
- Spec Agent 已升级为 LLM function calling：`backend/app/services/spec_agent_service.py`
- Trace Agent 已升级为 LLM function calling：`backend/app/services/trace_agent_service.py`
- Verifier Agent 已升级为“规则评分 + 单轮批量 LLM 复核”的混合模式：`backend/app/services/verifier_service.py`
- Probe Agent 已升级为“规则回退 + 单轮批量 LLM probe planning”的混合模式：`backend/app/services/probe_service.py`
- FTP parser 已扩展到更多 ProFuzzBench 观察到的 FTP 命令与参数格式：`backend/app/tools/ftp_parser.py`
- 已支持协议 schema、增强 seeds、feedback 报告三类 artifact 导出：`protocol_schema_*.json`、`generated_seeds_*.json`、`feedback_report_*.json`
- Trace / Probe 已补强 FTP 数据通道语义，能显式建模 `DATA_CHANNEL_READY` 以及 `PASV` / `EPSV` / `PORT` / `EPRT` 到传输类命令的关系
- 后端已新增轻量级 pipeline runtime 跟踪，可暴露当前 stage、stage 状态与阶段摘要，供 WebUI 轮询展示
- 前端已开始切换到共享项目上下文，不再把结果页固定绑死到单一 `projectId`
- Trace fallback / heuristic augmentation 已补入 `RNFR` / `RNTO` / `REIN` 以及更多 post-auth 自环命令，孤立状态问题已明显缓解
- `REIN` 语义已在 trace 落盘、seed 生成、probe 命令生成三层统一到 `RESETTING` 中间态，并通过 `data/outputs/evaluation_report_13.json` 验证 fallback 路径下不再回落到直接 `INIT`
- FTP parser 已修正对 `STOR` / `APPE` payload 的误识别，不再把 `prueba` / `CAPITULO...` 这类数据内容错误建模成 `PRUE` / `CAPI` 命令
- 已新增 `backend/app/protocols/` 协议层骨架、`ProtocolAdapter` / `ProtocolRegistry` 与 `FTPProtocolAdapter`，Spec / Trace / Probe / artifact / runner 已开始通过 adapter 获取协议差异能力
- `scripts/run_full_analysis.py` 已支持协议参数入口，`python3 scripts/run_full_analysis.py FTP` 已完成回归验证
- 评估结果已更新导出到 `data/outputs/evaluation_report_14.json`
- Trace Agent 已完成单工具 agent-first 稳定化：`record_trace_analysis` 单次调用同时承载 `observations + final analysis`，避免 provider 单轮只返回 observation 时触发回退
- 连续回归 `data/outputs/evaluation_report_20.json` 与 `data/outputs/evaluation_report_21.json` 已验证：`llm_tool_calls.trace_agent=1`、`fallback_used.trace_agent=False`、`message_types=39`，且已清除带斜杠伪 message type
- 评估报告已新增 agent 路径可观测字段：`llm_tool_calls.probe_agent`、`agent_path_signals`、`claim_provenance_distribution`，用于区分 `agent-derived` 与 `fallback-derived` 产物来源
- 最新验证 `data/outputs/evaluation_report_28.json`：`spec/trace/probe` 均有 tool call，`trace_agent` 未回退，`transition provenance` 为 `agent=21 fallback=0`，message types 仍保持 `39`
- Trace 覆盖护栏已完成配置化：`trace_augmentation_min_transitions` 与 `trace_augmentation_priority_messages` 已下沉到 adapter，Trace service 不再硬编码阈值与补齐命令集
- 最新验证 `data/outputs/evaluation_report_29.json`：`spec/trace/probe` 均有 tool call，`trace_agent` 未回退，`transition provenance` 为 `agent=18 fallback=2`，总转移数稳定在配置阈值 `20`
- 运行脚本已支持并发加速：`run_full_analysis.py` 可在可行时并行执行 Spec 与 Trace（环境变量 `ANALYSIS_PARALLEL_SPEC_TRACE=1`），以提升 API 请求吞吐
- 协议适配层已扩展并注册 `SMTP`、`RTSP`、`HTTP`（通用文本协议 adapter 骨架），协议切换入口可直接使用 `python3 scripts/run_full_analysis.py <PROTOCOL>`
- 已验证 `SMTP`、`RTSP`、`HTTP` 路径可运行并导出完整报告链路；4 个协议均已具备专属 adapter、parser、probe executor、seeds、traces 与文档摘要，但除 FTP 外其余协议仍处于“可运行、待强化评估”的阶段

#### 多协议闭环第一阶段（2026-04-26 本轮完成）

- **专属 adapter 实装**：SMTP / RTSP / HTTP 从通用骨架升级到独立 adapter 模块，各含专属 parser、状态机启发式与 probe executor
  - `backend/app/protocols/smtp/__init__.py` — SMTP adapter：DATA 体收集、AUTH 机制识别、RSET 状态回退、9 状态 + 18 条转移的启发式模型
  - `backend/app/protocols/rtsp/__init__.py` — RTSP adapter：header-aware 解析（CSeq / Session / Transport / Range）、7 状态 + 13 条转移、GET_PARAMETER / SET_PARAMETER 支持
  - `backend/app/protocols/http/__init__.py` — HTTP adapter：request-line + 关键 header 提取、8 状态机含 AUTH_REQUIRED / REDIRECT / ERROR、PUT / DELETE / PATCH / HEAD / OPTIONS 方法覆盖
- **Registry 升级**：`registry.py` 已切换到专属 adapter 类，不再使用 `GenericTextProtocolAdapter` 骨架填充 SMTP/RTSP/HTTP
- **ProFuzzBench 种子补齐**：新建 `data/traces/profuzzbench/smtp/`（5 raw）、`rtsp/`（3 raw）、`http/`（3 raw）
  - SMTP seeds：基础事务、AUTH LOGIN + RSET、多 RCPT TO、NOOP/VRFY、SIZE 扩展 + 二次事务
  - RTSP seeds：完整 OPTIONS→DESCRIBE→SETUP→PLAY→TEARDOWN、PLAY/PAUSE/PLAY 循环、404 错误恢复 + GET_PARAMETER
  - HTTP seeds：基础 GET/POST 保活、401 认证 + PUT/DELETE/OPTIONS、HEAD + 重定向 + PATCH + 500 错误
- **协议文档摘要补齐**：新建 `data/docs/smtp_summary.md`、`rtsp_summary.md`、`http_summary.md`，供 Spec Agent 解析
- **会话 trace 补齐**：新建 `data/traces/smtp_sessions.txt`（5 sessions）、`rtsp_sessions.txt`（3 sessions）、`http_sessions.txt`（3 sessions）
- **SMTP 服务器修复**：`scripts/start_smtp_server.py` 已替换废弃的 `smtpd`/`asyncore`（Python 3.12 已移除），改为 aiosmtpd 优先路径 + 纯 asyncio TCP fallback 双路实现
- **ProFuzzBench 导入脚本**：`scripts/fetch_profuzzbench_data.py` 支持 `--from-local` 与 `--zip-url` 两种导入路径，自动按协议关键词归类到 `data/traces/profuzzbench/<protocol>/`
- **import 修复**：修正 `generic_text_adapter.py` 相对 import 深度（`...core.config` → `..core.config`），确保新 subpackage 在标准 `sys.path` 下正常加载
- **验收验证**：`python3` 直接验证 import chain，4 个 adapter 全部成功加载：`FTP seeds=39 traces=10`、`SMTP seeds=5 traces=5`、`RTSP seeds=3 traces=3`、`HTTP seeds=3 traces=3`

### 当前推荐运行方式

课程作业阶段，优先针对单个协议执行完整分析，并导出统一格式的评估报告。

例如先启动对应本地服务：

```bash
python3 scripts/start_ftp_server.py
```

再执行完整分析流程：

```bash
python3 scripts/run_full_analysis.py FTP
```

切换其他已接入文本协议时使用：

```bash
python3 scripts/run_full_analysis.py SMTP
python3 scripts/run_full_analysis.py RTSP
python3 scripts/run_full_analysis.py HTTP
```

如果只想验证 provider 的 function calling 能力，使用：

```bash
python3 scripts/test_llm_single_turn_tools.py
```

### 当前评估结果摘要

#### 四协议统一纯 Agent 模式验证结果

> 运行时间：2026-04-26  
> 脚本：`python3 scripts/compare_protocols.py FTP SMTP RTSP HTTP`  
> 所有 rule-based fallback 路径已禁用，LLM 最多重试 5 次，失败即退出

| 指标 | FTP | SMTP | RTSP | HTTP |
|------|-----|------|------|------|
| 输入（doc / trace / seeds） | 1 / 10 / 39 | 1 / 5 / 5 | 1 / 3 / 3 | 1 / 3 / 3 |
| Message Types | `39` | `14` | `7` | `9` |
| States | `8` | `7` | `6` | `5` |
| Transitions | `14` | `16` | `2` | `11` |
| Probe Runs | `3` | `3` | `2` | `3` |
| Spec Agent LLM calls | `1` ✅ | `1` ✅ | `1` ✅ | `1` ✅ |
| Trace Agent LLM calls | `1` ✅ | `1` ✅ | `2` (重试1次) ✅ | `2` (重试1次) ✅ |
| Spec fallback 触发 | 否 | 否 | 否 | 否 |
| Trace fallback 触发 | 否 | 否 | 否 | 否 |
| Transition provenance (agent) | `14` | `16` | `2` | `11` |
| Transition provenance (fallback) | `0` | `0` | `0` | `0` |

**关键观察**：
- ✅ **四协议全程无 Fallback**：即使遇到了偶尔的连接错误（如 RTSP 和 HTTP Trace Agent 首次请求失败），重试机制（5次上限）也成功挽救了流程。`Transition provenance` 中 fallback 标志清零（`Fall↑ = 0`），证明全流程依赖大模型分析。
- ⚠️ **RTSP 数据极度不足**：RTSP trace 和 seed 样本过少（各只有3条），导致提取的 Message Types 只有 7 个，Transitions 只有 2 条。需要增加 ProFuzzBench 导出的 trace 文件来提升覆盖率。

#### 稳定性回归测试结果 (3 Round)

> 运行时间：2026-04-26  
> 脚本：`python3 scripts/run_regression.py --rounds 3 --protocols FTP SMTP`

| 协议 | 指标 | Min | Max | Mean | StDev | 是否稳定 |
|------|------|-----|-----|------|-------|----------|
| FTP | message_types | 39 | 39 | 39.0 | 0.0 | ✅ |
| FTP | states | 8 | 8 | 8.0 | 0.0 | ✅ |
| FTP | transitions | 15 | 20 | 17.67 | 2.517 | ⚠️ (波动) |
| SMTP | message_types | 12 | 12 | 12.0 | 0.0 | ✅ |
| SMTP | states | 7 | 10 | 8.0 | 1.732 | ⚠️ (波动) |
| SMTP | transitions | 14 | 17 | 15.0 | 1.732 | ⚠️ (波动) |

**稳定性分析**：
1. **静态解析（Spec Agent）极度稳定**：由于基于 RFC 样板，`message_types` 的提取在各轮中表现出 0 波动（FTP 恒定 39，SMTP 恒定 12）。
2. **动态推断（Trace Agent）存在幻觉/遗漏**：在完全剔除规则集硬编码增强后，纯 LLM 从 trace 日志中提取 `transitions` 的数量会出现 15%~20% 的浮动。这是因为大模型在理解连续会话片段时，偶尔会忽略某些次要消息。这正是我们在架构设计中引入 Probe（探索验证）和 Invariant（规则对抗）要解决的核心痛点。
### WebUI 适配状态

为了匹配“agent 系统完整分析协议并跑通 ProFuzzBench”的目标，WebUI 目前已开始同步适配以下能力：

- Dashboard 支持读取当前项目的 `analysis-summary`
- Dashboard 支持展示 pipeline runtime、stage 进度、artifact 摘要、推荐动作与待建模命令
- 后端已提供 `runtime` 与 `analysis-summary` 风格接口，避免前端自行拼接过多请求
- 状态机页、消息页、证据链页、probe 历史页正在统一改为读取共享项目上下文，而不是写死单项目
- 最近一次完整验证已完成前端依赖安装与构建通过，WebUI 能承接最新 runtime / artifact 展示改动

这意味着 WebUI 不再只是“静态结果展示层”，而是要逐步演进成 protocol-analysis agent 的运行控制台。

### 方向 B：数据通道状态语义增强

这一轮新增了对 FTP 数据通道准备阶段的显式建模，重点覆盖：

- `PASV` / `EPSV` / `PORT` / `EPRT` → `DATA_CHANNEL_READY`
- `DATA_CHANNEL_READY` → `LIST` / `NLST` / `MLSD` / `RETR` / `STOR` / `APPE` → `DATA_TRANSFER`
- `MLST` / `SIZE` / `STAT` 保持在 `AUTHENTICATED` 语义附近，而不是错误归入数据传输态
- `REIN` 对应 `RESETTING` 语义，用于后续继续补强 reset / retry 类实验

当前最新状态机里，已经可以看到以下新增或更清晰的状态：

- `DATA_CHANNEL_READY`
- `DATA_TRANSFER`
- `RESETTING`

其中 `RNFR -> RENAME_PENDING -> RNTO` 与 `REIN` 相关 reset 语义已经不再只停留在 schema / seed 层，而是能进入实际 state-machine 转移集合；最新 feedback 中 `isolated_states` 已下降到 `[]`。

在后续一次针对 reset 语义的专项验证中，`REIN` 已稳定表现为：

- `AUTHENTICATED -> RESETTING -> AUTH_PENDING -> AUTHENTICATED`
- 不再在 fallback 结果里重新引入 `AUTHENTICATED -> INIT via REIN`

而在最新一次 parser 清洗后，`PRUE` / `CAPI` 已确认只是 `APPE` / `STOR` 后的 payload 文本，不再被错误提升为 message type；同时真实观察到的 `ACCT` / `SMNT` 已落入 `AUTHENTICATED` 自环语义。

同时生成的增强 seeds 已覆盖更多数据通道实验模式，例如：

- `epsv_then_mlsd`
- `pasv_then_retr`
- `port_then_list`
- `eprt_then_mlsd`

### 当前 function calling 约束与实现策略

当前 provider 的 OpenAI-compatible 接口支持单轮 function calling，但在多轮 tool continuation 场景下会触发缺失 `thought_signature` 的服务端错误。因此当前实现采用以下策略：

- `llm_client.py` 使用单轮请求，不做多轮 tool continuation
- `tool_choice` 使用 `required`
- Spec Agent 改为一次性返回 `message_types[]`、`ordering_rules[]`、`field_constraints[]`
- Trace Agent 改为一次性返回 `observations`、`states[]`、`transitions[]`、`observed_message_types[]`
- Spec / Trace / Verifier / Probe 均已补充 best-effort fallback，provider 连接异常时不会直接打断全流程
- SDK 默认重试已关闭，便于快速暴露真实报错

这意味着当前方案优先保证稳定性与可跑通性，而不是依赖 provider 的多轮 tool loop 行为。

### 当前已知限制

- Verifier / Probe 虽已具备单轮批量 LLM 辅助，但目前仍保留强规则回退逻辑，属于混合模式而非纯 LLM 模式
- 当前虽然已压低“过度 supported”问题，但 probe 覆盖率相对转移数仍偏低，后续需要继续扩大在线验证比例
- `RESETTING` 等新状态已经出现，但连通性仍较弱，后续需要更定向的 reset / retry seeds
- 当前已不存在 `unused_message_types`，后续优化重点已从“补消息语义”转向“提升弱转移的 probe 支撑强度”
- `REIN` 语义虽已统一到 `RESETTING` 中间态，但相关转移目前仍大多是 `hypothesis`，后续需要继续通过 probe 提升支撑强度
- 当前系统更适合文本协议课程作业场景；对复杂二进制协议仍需额外解析层支持
- 当前与 ProFuzzBench 的关系主要是复用其部分 seeds / traces / target 经验，尚未覆盖完整协议谱系，也不以此作为当前阶段硬性目标

### 协议扩展现状

| 协议 | Adapter | Parser | 状态机 | Probe Executor | seeds | trace | 文档摘要 | 启动脚本 |
|------|---------|--------|--------|----------------|-------|-------|----------|----------|
| FTP  | 完整专属 | 完整专属 | 9+ 状态 | 完整 | 39 raw | 10 sessions | ftp_summary.md | start_ftp_server.py |
| SMTP | 完整专属 | 完整专属 | 9 状态  | 完整 | 5 raw  | 5 sessions  | smtp_summary.md | start_smtp_server.py |
| RTSP | 完整专属 | 完整专属 | 7 状态  | 完整 | 3 raw  | 3 sessions  | rtsp_summary.md | start_rtsp_server.py |
| HTTP | 完整专属 | 完整专属 | 8 状态  | 完整 | 3 raw  | 3 sessions  | http_summary.md | start_http_server.py |

- 当前已实现并注册的协议适配器：FTP、SMTP、RTSP、HTTP（均为独立专属 adapter 模块）
- **当前扩展阶段：多协议完整闭环** —— 4 个协议均具备 parser + 状态机 + probe executor + 数据输入 + 目标启动脚本，import 验证通过
- ProFuzzBench 数据导入工具：`scripts/fetch_profuzzbench_data.py` 支持 `--from-local` 与 `--zip-url` 两种导入路径
- 运行任意协议：`python3 scripts/run_full_analysis.py SMTP|RTSP|HTTP|FTP`

从课程作业目标看，当前优先级不是继续快速扩协议数量，而是：

- 先把 FTP、SMTP、RTSP、HTTP 四个协议做成统一、稳定、可比较的分析子集
- 优先补齐每个协议的标准化评估报告与展示材料
- 如需继续扩展协议，优先考虑 SIP、POP3 等较简单文本协议
- 暂不优先推进 TLS、SSH、DTLS、DICOM 等高复杂度协议

---

## 二、推荐技术栈

### 后端

- Python 3.11+
- FastAPI
- Pydantic
- NetworkX
- SQLModel 或 SQLAlchemy
- Uvicorn

### AI / Agent

- 任意支持 function calling 的 LLM API
- LangGraph / 自定义 agent orchestration 均可

### 前端

- React + TypeScript
- Vite
- Ant Design 或 shadcn/ui
- React Flow 或 Cytoscape.js 用于状态机可视化
- ECharts 或 Chart.js 用于统计图展示

### 存储

- SQLite 起步
- JSON 文件作为原始 artifact 缓存

### 协议输入处理

- pyshark 或 scapy 解析 pcap
- 自定义文本协议 parser

---

## 三、第一期交付边界

第一期只要求实现最小可运行版本：

- 重点协议：FTP
- 输入来源：文档摘要、trace、在线交互日志
- 智能体：Spec Agent、Trace Agent、Verifier Agent、Probe Agent
- 课程展示目标：能够输出消息类型、粗粒度状态、候选转移、证据链和 probe 修正案例
- 可选暂缓：Code Agent
- 前端页面：总览页、状态机页、证据链页、Probe 历史页

不要求：

- 支持复杂二进制协议
- 大规模 fuzzing
- 完整 RFC 自动解析
- 全自动高精度状态机恢复
- 完整 ProFuzzBench 全协议覆盖
- 与现有 fuzzing 论文做严格性能对比

---

## 四、目录结构建议

```text
project/
  backend/
    app/
      api/
      core/
      models/
      schemas/
      services/
      agents/
      tools/
      storage/
      tests/
    main.py
    requirements.txt
  frontend/
    src/
      api/
      components/
      pages/
      hooks/
      types/
    package.json
  data/
    samples/
    traces/
    docs/
    outputs/
  scripts/
  README.md
```

---

## 五、开发任务拆解

## Task 1：项目初始化

### 目标
搭建前后端工程骨架，确保本地可启动。

### 子任务
- 初始化 `backend` FastAPI 项目
- 初始化 `frontend` React + TypeScript 项目
- 配置开发环境和依赖
- 编写顶层 README
- 配置 `.env.example`

### 验收标准
- 后端 `http://localhost:8000/docs` 可访问
- 前端 `http://localhost:5173` 可访问
- README 包含启动方式

---

## Task 2：定义领域模型与数据库结构

### 目标
建立系统核心数据对象。

### 需要定义的模型

#### ProtocolProject
- `id`
- `name`
- `protocol_name`
- `description`
- `created_at`

#### SessionTrace
- `id`
- `project_id`
- `source_type` (`doc`, `trace`, `probe`, `code`)
- `raw_content`
- `parsed_content`
- `created_at`

#### MessageType
- `id`
- `project_id`
- `name`
- `template`
- `fields_json`
- `confidence`

#### ProtocolState
- `id`
- `project_id`
- `name`
- `description`
- `confidence`

#### Transition
- `id`
- `project_id`
- `from_state`
- `to_state`
- `message_type`
- `confidence`
- `status` (`hypothesis`, `supported`, `disputed`)

#### Invariant
- `id`
- `project_id`
- `rule_text`
- `rule_type`
- `confidence`
- `status`

#### Evidence
- `id`
- `project_id`
- `claim_type` (`transition`, `invariant`, `field_constraint`)
- `claim_id`
- `source_type`
- `source_ref`
- `snippet`
- `score`

#### ProbeRun
- `id`
- `project_id`
- `target_host`
- `target_port`
- `goal`
- `request_payload`
- `response_payload`
- `result_summary`
- `created_at`

### 验收标准
- 数据表可自动创建
- 提供基础 CRUD
- 能通过 API 创建一个 project

---

## Task 3：协议中间表示与解析器

### 目标
把输入数据转成统一格式。

### 子任务
- 定义协议中间表示 `ProtocolEvent`
- 实现文本协议消息解析器
- 实现 FTP 基础 parser
- 支持从 JSON / 文本日志导入 session trace
- 支持简单 pcap 解析后转成应用层消息

### 建议输出结构

```json
{
  "direction": "client_to_server",
  "raw": "USER anonymous\\r\\n",
  "message_type": "USER",
  "fields": {
    "username": "anonymous"
  },
  "response": {
    "code": "331",
    "raw": "331 User name okay, need password."
  }
}
```

### 验收标准
- 能导入至少 5 条 FTP 会话样本
- 能正确识别 `USER`、`PASS`、`LIST`、`PWD`、`QUIT`

---

## Task 4：工具调用接口层

### 目标
为 agent 提供固定工具函数。

### 需要实现的工具
- `extract_message_types(input_sessions)`
- `extract_fields_and_constraints(input_sessions)`
- `infer_candidate_states(input_sessions)`
- `propose_transitions(states, messages)`
- `score_evidence(claim, evidence_list)`
- `generate_probe(model_snapshot, ambiguity)`
- `update_protocol_model(model_snapshot, new_observation)`

### 要求
- 每个工具都要有纯 Python 实现入口
- 每个工具都要有清晰输入输出 schema
- 工具输出必须是结构化 JSON，而不是自由文本

### 验收标准
- 本地脚本可直接调用这些工具
- 每个工具至少有 1 个单元测试

---

## Task 5：Spec Agent 实现

### 目标
从协议文档摘要中提取消息类型、字段语义和顺序规则。

### 子任务
- 设计 prompt
- 接入 LLM function calling
- 限制模型只通过工具接口输出
- 支持输入 FTP 文档摘要

### 输出内容
- 候选消息类型
- 字段说明
- 顺序依赖
- 候选协议规则

### 验收标准
- 对 FTP 摘要，能提取 `USER`、`PASS`、`QUIT` 等消息
- 输出为标准 JSON

---

## Task 6：Trace Agent 实现

### 目标
从 trace 中恢复消息模式、响应模式和粗粒度状态簇。

### 子任务
- 对会话序列做消息统计
- 基于响应码和上下文做简单状态聚类
- 输出候选状态和转移边
- 支持从多条 FTP 会话中恢复粗状态图

### 验收标准
- 能输出类似 `INIT`、`AUTH_PENDING`、`AUTHED` 的候选状态
- 至少输出 5 条候选转移

---

## Task 7：Verifier Agent 实现

### 目标
对来自不同来源的结论做证据绑定和一致性核验。

### 子任务
- 定义 claim 抽象
- 将 transition / invariant / field constraint 与 evidence 绑定
- 为 claim 计算 `confidence` 和 `status`
- 支持将结论标为 `hypothesis`、`supported`、`disputed`

### 验收标准
- 每条 transition 可关联 1 条以上 evidence
- 冲突证据会导致状态变为 `disputed`

---

## Task 8：Probe Agent 与在线探测执行器

### 目标
对低置信度结论生成判别性输入，并在线执行。

### 子任务
- 实现 probe 目标描述格式
- 实现 FTP 交互执行器
- 支持向目标服务发送消息并记录响应
- 根据 probe 结果更新状态机或不变量

### 示例目标
- 验证 `PASS` 是否必须在 `USER` 之后
- 验证 `LIST` 是否要求认证成功

### 验收标准
- 能成功连接本地 FTP 服务
- 能记录 request / response
- 能根据 probe 结果修正至少 1 条 transition 或 invariant

---

## Task 9：协议模型管理器

### 目标
统一维护状态、转移、消息类型、不变量和版本历史。

### 子任务
- 设计 `ProtocolModelManager`
- 支持模型快照保存
- 支持对 transition 和 invariant 做版本更新
- 支持导出完整 JSON artifact

### 验收标准
- 每次 probe 后可生成新版本快照
- 任一项目可导出完整模型 JSON

---

## Task 10：后端 API 设计与实现

### 目标
为前端和自动化流程提供统一接口。

### 建议 API

#### 项目管理
- `POST /projects`
- `GET /projects`
- `GET /projects/{id}`

#### 数据导入
- `POST /projects/{id}/import/doc`
- `POST /projects/{id}/import/trace`
- `POST /projects/{id}/import/code`

#### 分析执行
- `POST /projects/{id}/run/spec-agent`
- `POST /projects/{id}/run/trace-agent`
- `POST /projects/{id}/run/verifier`
- `POST /projects/{id}/run/probe`
- `POST /projects/{id}/run/full-pipeline`

#### 结果查询
- `GET /projects/{id}/states`
- `GET /projects/{id}/transitions`
- `GET /projects/{id}/invariants`
- `GET /projects/{id}/evidence`
- `GET /projects/{id}/probes`
- `GET /projects/{id}/model/export`

### 验收标准
- 所有核心资源可通过 API 获取
- Swagger 文档完整可用

---

## Task 11：WebUI 设计与实现

### 目标
实现分析过程和结果的可视化。

### 页面一：Dashboard
显示：
- 项目名称
- 协议类型
- 消息类型数
- 状态数
- transition 数
- invariant 数
- probe 次数
- disputed 结论数

### 页面二：状态机视图
要求：
- 使用 React Flow 或 Cytoscape.js 绘制图
- 点击边后显示：触发消息、目标状态、confidence、status
- 展示关联 evidence 列表

### 页面三：消息与字段视图
要求：
- 列出消息类型
- 展示字段、模板、约束和依赖

### 页面四：证据链视图
要求：
- 按 claim 分组展示 evidence
- 支持点击查看原始 snippet

### 页面五：Probe 历史页
要求：
- 显示 probe 目标
- 显示请求和响应
- 显示该次 probe 导致的模型变更

### 验收标准
- 页面可访问
- 状态图可交互
- 任意 transition 可查看 evidence

---

## Task 12：样例数据与 Demo 环境

### 目标
提供可演示的数据和目标服务。

### 子任务
- 准备 FTP 协议摘要文档
- 准备至少 10 条 FTP 会话样本
- 提供本地 FTP 服务启动脚本
- 提供最小 demo 数据导入脚本

### 建议目标服务
- pyftpdlib
- 或容器化轻量 FTP 服务

### 验收标准
- 一键脚本可启动 demo 环境
- 导入样本后能跑完整流程

---

## Task 13：端到端流程联调

### 目标
打通完整分析链路。

### 目标流程
1. 创建项目
2. 导入 FTP 文档摘要
3. 导入 trace 样本
4. 运行 Spec Agent
5. 运行 Trace Agent
6. 运行 Verifier Agent
7. 针对 disputed 结论触发 Probe Agent
8. 更新协议模型
9. 在 WebUI 中查看结果

### 验收标准
- 上述 9 步全部可跑通
- 能在 UI 中看到状态图和证据链

---

## Task 14：实验与评估支持

### 目标
支持课程论文中的实验与对比。

### 子任务
- 输出消息类型识别统计
- 输出 transition 数量和状态数量统计
- 输出 `hypothesis / supported / disputed` 数量分布
- 输出 probe 前后模型变化
- 预留消融开关：
  - 关闭 Verifier
  - 关闭 Probe
  - 单 agent 模式
- 对 FTP、SMTP、RTSP、HTTP 生成统一格式的课程展示报告

### 验收标准
- 能导出实验结果 JSON
- 能生成简单图表或 CSV

---

## 六、开发优先级

### P0
- 四个已接入文本协议的统一评估口径
- FTP / SMTP 的重点展示结果固化
- Spec / Trace / Verifier / Probe 主链路稳定性
- 基础 API
- 状态机页与证据链页可展示最新结果

### P1
- RTSP / HTTP 展示材料补齐
- Probe 结果与模型修正案例整理
- Dashboard 与运行态可观测性完善
- 连续回归与结果导出

### P2
- 新增简单文本协议（如 SIP、POP3）
- Code Agent
- 更完整的实验与统计输出
- 复杂 trace 导入

---

## 七、建议迭代计划

### 近期建议计划

#### 第一步：收口现有四协议
- 分别跑通 FTP、SMTP、RTSP、HTTP 的完整分析流程
- 为四个协议导出统一格式的 evaluation report
- 统计 message types、states、transitions、evidence、probe、agent/fallback 占比

#### 第二步：强化课程展示主线
- 以 FTP 作为主展示协议，整理完整端到端案例
- 以 SMTP 作为第二展示协议，证明多协议迁移能力
- 将 RTSP、HTTP 作为补充展示协议，证明 adapter 机制具有泛化能力

#### 第三步：轻量利用 ProFuzzBench
- 将 ProFuzzBench 作为 seeds / traces 来源补充现有样本
- 重点补充四个已接入协议，而非追求完整 benchmark
- 观察补充样本后 message types 与 transitions 是否更丰富

#### 第四步：按需扩展简单文本协议
- 若时间允许，再新增 SIP、POP3 等简单文本协议
- 不在课程作业阶段优先推进 TLS、SSH、DTLS 等高难协议

---

## 八、最低验收标准

项目至少需要满足以下条件：

1. 至少稳定支持 FTP，并能展示多协议扩展到 SMTP / RTSP / HTTP
2. 能导入文档摘要和 trace 样本
3. 能输出消息类型、候选状态、候选转移
4. 每条 transition 至少可绑定证据
5. 能通过 probe 修正至少一条结论
6. WebUI 可展示状态图与证据链
7. 可以导出统一格式的分析结果 JSON / report

---

## 九、附加建议

### 关于模型调用
- 不要让模型自由生成最终报告
- 强制使用 function calling / JSON schema
- 对关键输出做 schema 校验

### 关于协议范围
- 当前阶段以 FTP、SMTP、RTSP、HTTP 四个文本协议为主
- 课程展示重点优先放在 FTP 与 SMTP
- 如需扩展，优先增加简单文本协议，不优先做复杂二进制协议

### 关于展示
- 优先把状态图和证据链做漂亮
- probe 历史页对答辩展示很重要
- UI 里最好能展示“这条边为什么存在”

### 关于代码质量
- 核心工具函数写单元测试
- 所有 agent 输出落盘为 JSON artifact
- 所有流程保留可复现日志

## 九点五、下一阶段直接执行建议

按照当前课程作业目标，下一阶段建议直接执行以下事项：

1. ✅ 不再优先扩展高复杂度新协议，先完成 FTP、SMTP、RTSP、HTTP 四个协议的统一报告导出
   - 实装：`scripts/compare_protocols.py` — 批量运行 4 个协议，输出统一对比表 + `data/outputs/multi_protocol_comparison.json`
2. ✅ 将 ProFuzzBench 视为 seeds / traces 来源，补充这四个协议的输入样本（seeds/traces 已在上一阶段全部补齐）
3. ✅ 固化 FTP 的完整展示案例，并补一个 SMTP 的完整展示案例
   - 实装：已完成首次纯 Agent 模式验证（FTP: 39 msg_types / 8 states / 20 transitions；SMTP: 12 msg_types / 9 states / 12 transitions）
   - 报告已导出至 `data/outputs/multi_protocol_comparison.json`，评估结果已同步至文档"当前评估结果摘要"节
4. ✅ 为 RTSP、HTTP 准备较简洁的补充展示材料，重点展示 adapter 与 agent-first 分析流程可迁移
   - 实装：4 个协议均已完整闭环，可用 `python3 scripts/run_full_analysis.py RTSP|HTTP` 直接跑出展示报告
5. ✅ 在 WebUI 中突出展示状态图、证据链、probe 修正和 agent/fallback 来源分布
   - 实装：Dashboard 新增 **Agent Path Signals** 面板：每个 agent 的 LLM tool calls 计数 + fallback 状态标签 + transition provenance 比例条
   - 实装：`/projects/{id}/analysis-summary` 扩展 `agent_path` 字段（spec/trace/probe fallback 信号 + evidence 来源分布）
   - 实装：StateMachine 节点颜色扩展支持 SMTP / RTSP / HTTP 状态名；未知状态通过 hash 映射到精选色板，不再显示统一蓝色

### 当前仍需继续执行的代码事项

结合当前运行结果，后续代码层面最值得继续推进的不是扩展高难协议，而是把现有四个文本协议的分析、验证与展示链路做实。建议按以下顺序执行：

1. ✅ **补齐四协议统一评估导出**
   - 确认 `scripts/compare_protocols.py` 能稳定覆盖 FTP、SMTP、RTSP、HTTP 四个协议
   - 统一导出字段：`message_types`、`states`、`transitions`、`invariants`、`evidence_records`、`probe_runs`、`supported/hypothesis/disputed`、`llm_tool_calls`、`fallback_used`、`provenance_distribution`
   - 确保输出 JSON 与 markdown 中的统计口径一致，避免脚本结果和文档结果脱节

2. ✅ **优先补强 probe 的“可验证性”而不是继续补 message types**
   - 针对 FTP 增加更容易确认的 probe 目标，例如 `LIST` 是否要求认证、`RNTO` 是否依赖 `RNFR`
   - 针对 SMTP 增加 `DATA` 是否依赖 `MAIL FROM/RCPT TO`、`QUIT` 是否全局可达等 probe
   - 优先把少量 `hypothesis` 转成 `supported` 或 `disputed`，作为课程展示中的关键闭环证据

3. ✅ **把 RTSP / HTTP 跑出与 FTP / SMTP 同口径的结果文件**
   - 不要求一开始就达到 FTP 的覆盖度
   - 但至少要能稳定导出 message/state/transition/evidence/probe 统计
   - 若某协议当前 probe executor 较弱，先保证报告字段完整，再逐步补强验证能力

4. ✅ **收紧 fallback 残留来源的可解释性**
   - 当前报告中仍存在少量 `transition provenance (fallback)`，需要在 artifact 中明确区分它们来自哪一层（probe evidence、trace augmentation 或规则护栏）
   - 建议在 `analysis-summary` 和 evaluation report 中补充更细的 fallback 来源字段，避免答辩时只能口头解释

5. ✅ **补一轮四协议连续回归**
   - 对 FTP、SMTP、RTSP、HTTP 分别至少连续跑 3 轮
   - 检查 message types 是否抖动、transition 数是否明显回落、fallback 是否突然升高
   - 将连续回归结果整理成单独 artifact，作为“系统稳定性”证据

6. ✅ **继续完善 WebUI 的结果承接，而不是扩新页面**
   - 优先保证 Dashboard、状态机页、证据链页能直接读取四协议统一结果
   - 将 `agent_path_signals`、`provenance_distribution`、`supported/hypothesis/disputed` 这些已经在后端产出的字段稳定展示出来
   - 暂时不优先增加复杂交互，先保证现有结果“看得见、讲得清、对得上”


---

## 十、最终交付清单

课程作业阶段最终需要交付：

- 可运行的前后端项目
- demo 数据集
- 本地启动脚本
- `.env.example`
- API 文档
- 端到端演示说明
- 实验导出样例
- 完整 README
