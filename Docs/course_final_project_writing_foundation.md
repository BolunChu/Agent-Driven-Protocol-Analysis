# 1. 项目定位与目标

本项目是一个面向文本网络协议的、多智能体驱动的协议分析系统原型，代码入口在 [backend/main.py](backend/main.py) 与 [frontend/src/App.tsx](frontend/src/App.tsx)。系统通过 Spec Agent、Trace Agent、Verifier Agent、Probe Agent 的链式执行，把文档摘要、会话 trace、seed 样本转成结构化协议模型、证据链与评估产物。

当前课程作业定位是“可运行、可解释、可展示”的 agent-first 原型，而不是工业级协议逆向平台。该定位可从以下实现共同验证：
- agent 流程编排在 [backend/app/services/pipeline_service.py](backend/app/services/pipeline_service.py)
- function calling 约束在 [backend/app/core/llm_client.py](backend/app/core/llm_client.py)
- 评估输出在 [data/outputs/evaluation_report_28.json](data/outputs/evaluation_report_28.json)、[data/outputs/multi_protocol_comparison.json](data/outputs/multi_protocol_comparison.json)、[data/outputs/regression_report.json](data/outputs/regression_report.json)

当前聚焦文本协议（FTP/SMTP/RTSP/HTTP）的原因是：
- 文本协议边界清晰，便于 parser 与 function calling 的结构化落地。
- 课程周期内可完成“抽取 message types、粗粒度状态、部分转移、证据绑定、在线 probe 修正、前端展示”的闭环。
- 仓库已有四协议文档摘要与 trace 资产，分别位于 [data/docs/ftp_summary.md](data/docs/ftp_summary.md)、[data/docs/smtp_summary.md](data/docs/smtp_summary.md)、[data/docs/rtsp_summary.md](data/docs/rtsp_summary.md)、[data/docs/http_summary.md](data/docs/http_summary.md) 以及 [data/traces](data/traces)。

当前主要目标（已在代码和产物中体现）是：
- agent-first 协议分析：分析主路径由 agent 工具调用驱动，不依赖手写全规则。
- 从文本协议中提取 message types、粗粒度状态、部分转移与证据链。
- probe 用于少量在线验证与修正，不承担全面覆盖。

当前不追求的目标：
- 不追求完整协议逆向或完整状态机恢复。
- 不追求 SOTA benchmark 指标。
- 不追求复杂二进制协议（如 TLS/SSH/DTLS）在当前阶段的完整支持。

ProFuzzBench 在本项目中的角色（按当前仓库实现）主要是 seeds/traces 样本来源，不是 benchmark 主战场：
- 导入脚本是 [scripts/fetch_profuzzbench_data.py](scripts/fetch_profuzzbench_data.py)
- 数据目录是 [data/traces/profuzzbench](data/traces/profuzzbench)
- FTP 当前读取根目录 raw seeds，SMTP/RTSP/HTTP 读取各自子目录 raw seeds（实现见 [backend/app/protocols/ftp/adapter.py](backend/app/protocols/ftp/adapter.py) 与 [backend/app/protocols/generic_text_adapter.py](backend/app/protocols/generic_text_adapter.py)）

# 2. 当前项目总体架构

系统是“后端 agent pipeline + 协议适配层 + artifact 导出 + API + WebUI”结构。

文字版架构图说明：
输入(doc/trace/seeds/本地服务) -> parser/adapter -> Spec Agent + Trace Agent -> Verifier -> Probe -> protocol schema/seed/feedback/evaluation artifacts -> FastAPI -> WebUI Dashboard/StateMachine/Evidence/Probe

## 2.1 架构分层

- 数据输入层：导入 doc、trace、seed 到 SessionTrace。
- 协议适配层：通过 ProtocolAdapter/ProtocolRegistry 抽象协议差异。
- LLM/function calling 接入层：统一在 call_with_tools 中执行单轮工具调用。
- Spec Agent：从文档和观测摘要抽取 message types + ordering/field constraints。
- Trace Agent：从会话恢复状态与转移，并记录 observations。
- Verifier Agent：对 transition/invariant 做 evidence scoring + LLM 复核 + guard。
- Probe Agent：选择高价值 claim 做在线探测并回写模型状态。
- 协议模型管理与 artifact 导出：导出 protocol_schema、generated_seeds、feedback。
- 后端 API 层：projects/run/runtime/analysis-summary 等接口。
- WebUI 展示层：Dashboard、State Machine、Messages、Evidence Chain、Probe History。

## 2.2 调用关系与数据流

调用主链由 [backend/app/services/pipeline_service.py](backend/app/services/pipeline_service.py) 固定：
- spec -> trace -> verifier -> probe -> artifacts -> seed_generation -> feedback

核心数据实体在 [backend/app/models/domain.py](backend/app/models/domain.py)：
- ProtocolProject
- SessionTrace
- MessageType
- ProtocolState
- Transition
- Invariant
- Evidence
- ProbeRun

所有阶段产出都会在 runtime 中记录 stage summary（[backend/app/services/runtime_service.py](backend/app/services/runtime_service.py)），并通过 [backend/app/api/projects.py](backend/app/api/projects.py) 暴露给前端。

## 2.3 为什么使用 ProtocolAdapter / ProtocolRegistry

- 协议差异（parser、prompt、state heuristic、probe executor、数据加载）集中在 adapter，减少 service 层硬编码。
- 统一入口按 protocol_name 分发，避免为每个协议复制流水线。
- 当前注册协议在 [backend/app/protocols/registry.py](backend/app/protocols/registry.py)：FTP/SMTP/RTSP/HTTP。

## 2.4 为什么采用 agent-first + fallback 兜底

- 设计目标是 agent-first：主路径依赖工具调用结果构建模型。
- 同时保留 fallback 方法（如 trace/spec 的 _apply_fallback），用于 provider 不可用时的兜底。
- 注意：Trace 里 heuristic augmentation 当前已显式禁用（注释写明 agent-only mode，见 [backend/app/services/trace_agent_service.py](backend/app/services/trace_agent_service.py)），因此“规则补齐”现在不是默认主路径。

## 2.5 为什么 function calling 是核心约束

- 使用工具 schema 强制结构化输出，避免自由文本难以落库和难以审计。
- llm client 中固定 tool_choice=required，见 [backend/app/core/llm_client.py](backend/app/core/llm_client.py)。
- Spec、Trace、Verifier、Probe 都是“单轮批量工具调用”风格。

## 2.6 为什么当前采用单轮 function calling

- 仓库内专门保留了多轮测试脚本 [scripts/test_llm_tool_loop.py](scripts/test_llm_tool_loop.py) 与单轮测试脚本 [scripts/test_llm_single_turn_tools.py](scripts/test_llm_single_turn_tools.py)。
- 当前实现选择单轮，是为了稳定性和 provider 兼容性（对应仓库记忆结论可在 [data/outputs/evaluation_report_20.json](data/outputs/evaluation_report_20.json)、[data/outputs/evaluation_report_21.json](data/outputs/evaluation_report_21.json) 看到 trace tool call=1 且 fallback=false 的稳定表现）。

# 3. 协议适配机制与多协议设计

当前支持 FTP、SMTP、RTSP、HTTP 的直接原因是仓库已具备完整闭环资产：
- adapter 已实现并注册
- parser 可运行
- probe executor 可连本地服务
- docs/traces/seeds/启动脚本均存在
- compare/regression 脚本已可产出统一对比结果

协议抽象核心在 [backend/app/protocols/base.py](backend/app/protocols/base.py)：
- 输入加载：load_doc_inputs/load_trace_inputs/load_seed_inputs
- prompt：spec_system_prompt/trace_system_prompt/probe_system_prompt
- 解析：parse_session/parse_trace
- 状态机：infer_candidate_states/propose_transitions/normalize_transition
- probe：select_probe_targets/generate_probe_commands/execute_probe

四协议角色建议（基于当前输出成熟度）：
- FTP：主展示协议（样本最多，结果最完整）
- SMTP：第二展示协议（结果成型但波动较 FTP 大）
- RTSP/HTTP：泛化展示协议（证明框架可迁移，覆盖仍偏轻）

当前不优先 TLS/SSH/DTLS 的原因：
- 现有 parser/probe 以文本请求响应为中心。
- 课程周期里优先把四文本协议结果做稳，比扩展高复杂协议更可交付。

后续扩展优先 SIP/POP3 这类简单文本协议更合理：
- 能复用现有 GenericTextProtocolAdapter 思路与现有前后端展示模型。
- 能在低改动成本下提升“多协议平台”说服力。

## 3.1 多协议实现对照表

| 协议 | adapter | parser | 状态机实现 | probe executor | seeds | traces | 文档摘要 | 启动脚本 | 当前成熟度判断 |
|---|---|---|---|---|---|---|---|---|---|
| FTP | [backend/app/protocols/ftp/adapter.py](backend/app/protocols/ftp/adapter.py) | [backend/app/tools/ftp_parser.py](backend/app/tools/ftp_parser.py) + adapter parse | adapter infer/propose + trace agent 写入 | adapter execute_probe(FTP socket) | [data/traces/profuzzbench](data/traces/profuzzbench) 根目录 39 raw | [data/traces/ftp_sessions.txt](data/traces/ftp_sessions.txt) 10 sessions | [data/docs/ftp_summary.md](data/docs/ftp_summary.md) | [scripts/start_ftp_server.py](scripts/start_ftp_server.py) | 高（课程展示主协议） |
| SMTP | [backend/app/protocols/smtp/__init__.py](backend/app/protocols/smtp/__init__.py) | SMTP 专属 parser | SMTP 专属 infer/propose | SMTP live probe | [data/traces/profuzzbench/smtp](data/traces/profuzzbench/smtp) 5 raw | [data/traces/smtp_sessions.txt](data/traces/smtp_sessions.txt) 5 sessions | [data/docs/smtp_summary.md](data/docs/smtp_summary.md) | [scripts/start_smtp_server.py](scripts/start_smtp_server.py) | 中高（第二展示协议） |
| RTSP | [backend/app/protocols/rtsp/__init__.py](backend/app/protocols/rtsp/__init__.py) | RTSP header-aware parser | RTSP 专属 infer/propose | RTSP live probe | [data/traces/profuzzbench/rtsp](data/traces/profuzzbench/rtsp) 3 raw | [data/traces/rtsp_sessions.txt](data/traces/rtsp_sessions.txt) 3 sessions | [data/docs/rtsp_summary.md](data/docs/rtsp_summary.md) | [scripts/start_rtsp_server.py](scripts/start_rtsp_server.py) | 中（泛化演示，样本偏少） |
| HTTP | [backend/app/protocols/http/__init__.py](backend/app/protocols/http/__init__.py) | HTTP request/response parser | HTTP 专属 infer/propose | HTTP live probe | [data/traces/profuzzbench/http](data/traces/profuzzbench/http) 3 raw | [data/traces/http_sessions.txt](data/traces/http_sessions.txt) 3 sessions | [data/docs/http_summary.md](data/docs/http_summary.md) | [scripts/start_http_server.py](scripts/start_http_server.py) | 中（泛化演示，样本偏少） |

# 4. 关键功能模块说明

## 4.1 输入数据处理

输入来源包含：
- 文档摘要：source_type=doc
- 会话 trace：source_type=trace
- seed 导入后同样以 trace 入库
- 本地协议服务 probe 交互（ProbeRun + Evidence）
- ProFuzzBench 数据导入

实现与脚本：
- 入库模型：SessionTrace，见 [backend/app/models/domain.py](backend/app/models/domain.py)
- 导入逻辑：run_full_analysis 中 import_data，见 [scripts/run_full_analysis.py](scripts/run_full_analysis.py)
- ProFuzzBench 导入： [scripts/fetch_profuzzbench_data.py](scripts/fetch_profuzzbench_data.py)

当前已实现并验证：
- 四协议 doc/trace/seed 输入链路均可跑通（见 [data/outputs/multi_protocol_comparison.json](data/outputs/multi_protocol_comparison.json) 的 import_stats）。

已有但待强化：
- FTP seeds 目录结构与其他协议不一致（FTP 在 profuzzbench 根目录 raw，其他在子目录），工程一致性可继续整理。

尚未完成：
- 自动 pcap 深解析并统一映射到多协议 parser（待仓库内进一步核实）。

## 4.2 Spec Agent

Spec Agent 输入：
- doc 内容
- trace 的观测摘要（由 adapter 组装）

Spec Agent输出：
- message_types
- ordering_rules
- field_constraints

约束方式：
- record_spec_analysis 单工具批量输出（见 [backend/app/services/spec_agent_service.py](backend/app/services/spec_agent_service.py)）。

结构化字段（落库后对应）：
- MessageType.name/template/fields_json/confidence
- Invariant.rule_text/rule_type/confidence/status
- Evidence.source_type/source_ref/snippet/score

当前状态：
- 已实现并验证（四协议 comparison 中 spec_llm_calls=1，spec_fallback=false）。

## 4.3 Trace Agent

Trace Agent 主要任务：
- 从会话恢复状态与转移
- 记录 observations（state_hypotheses/message_type_observations/sequence_patterns）

避免 provider 只返回 observation 的退化策略：
- 采用 record_trace_analysis 单工具，一次性包含 observations + final states/transitions，见 [backend/app/services/trace_agent_service.py](backend/app/services/trace_agent_service.py)。
- 稳定性证据见 [data/outputs/evaluation_report_20.json](data/outputs/evaluation_report_20.json) 与 [data/outputs/evaluation_report_21.json](data/outputs/evaluation_report_21.json)：trace_agent llm_tool_calls=1 且 fallback=false。

当前 trace fallback / augmentation 策略：
- fallback 函数仍保留（_apply_state_fallback）。
- heuristic augmentation 目前在主逻辑中禁用（agent-only mode 注释）。
- trace_augmentation_min_transitions 与 priority_messages 已下沉 adapter 接口，但当前主路径未启用自动补齐。

覆盖护栏与 adapter 配置化含义：
- 协议差异化阈值和优先 message 列表可由 adapter 提供，而不是写死在 trace service。

## 4.4 Verifier Agent

Verifier 的职责：
- 对 transition/invariant 拉取证据并打分
- 合并 heuristic + LLM review 结果
- 应用 evidence guard，限制 unsupported 场景被过早标记 supported

为什么需要 evidence 绑定：
- claim 没有证据链就无法解释来源，也不利于前端和报告复盘。

hypothesis/supported/disputed 的来源：
- 先由 score_evidence 给 heuristic status
- 再由 record_verification_review 提供 LLM 审核建议
- 最后经 _merge_status + _apply_evidence_guard 决定最终状态（实现见 [backend/app/services/verifier_service.py](backend/app/services/verifier_service.py)）

当前更像什么：
- 规则评分 + LLM 复核的混合型 verifier，而非纯 LLM。

## 4.5 Probe Agent

为什么要probe：
- 给低置信或争议 claim 增加在线可验证证据。

当前probe在做什么：
- 选取最多 3 个高价值 target
- LLM 先给 probe plan（record_probe_plan）
- adapter 执行在线交互
- 根据响应结果回写 claim 状态/置信度，并写 Evidence(source_type=probe)

本地协议服务如何参与：
- FTP 服务 [scripts/start_ftp_server.py](scripts/start_ftp_server.py)
- SMTP 服务 [scripts/start_smtp_server.py](scripts/start_smtp_server.py)
- RTSP 服务 [scripts/start_rtsp_server.py](scripts/start_rtsp_server.py)
- HTTP 服务 [scripts/start_http_server.py](scripts/start_http_server.py)

probe 当前已能做到：
- 四协议均可执行 probe runs（comparison 表中 probes 为 FTP 3、SMTP 3、RTSP 2、HTTP 3）。

仍欠缺：
- regression 报告中 probe_evidence 目前为 0，说明 probe 证据贡献尚未形成稳定增益（见 [data/outputs/regression_report.json](data/outputs/regression_report.json)）。

## 4.6 Artifact 导出与评估报告

产物链路：
- evaluation_report: 每次 run 全量摘要与 lists，见 [scripts/run_full_analysis.py](scripts/run_full_analysis.py)
- protocol_schema: 协议结构化导出，见 [backend/app/services/artifact_service.py](backend/app/services/artifact_service.py)
- generated_seeds: 迭代种子建议
- feedback_report: 迭代反馈与推荐动作
- multi_protocol_comparison: 四协议统一对比
- regression_report: 连续回归稳定性
- analysis-summary: 后端聚合给前端的统一摘要接口

对应文件：
- [data/outputs/evaluation_report_28.json](data/outputs/evaluation_report_28.json)
- [data/outputs/protocol_schema_28.json](data/outputs/protocol_schema_28.json)
- [data/outputs/generated_seeds_28.json](data/outputs/generated_seeds_28.json)
- [data/outputs/feedback_report_28.json](data/outputs/feedback_report_28.json)
- [data/outputs/multi_protocol_comparison.json](data/outputs/multi_protocol_comparison.json)
- [data/outputs/regression_report.json](data/outputs/regression_report.json)
- analysis-summary API： [backend/app/api/projects.py](backend/app/api/projects.py)

# 5. 当前运行方式与脚本入口

以下命令均来自仓库脚本，建议在项目根目录执行。

## 5.1 启动本地协议服务

1. FTP
python3 scripts/start_ftp_server.py

2. SMTP
python3 scripts/start_smtp_server.py

3. RTSP
python3 scripts/start_rtsp_server.py

4. HTTP
python3 scripts/start_http_server.py

## 5.2 运行单协议完整分析

1. FTP
python3 scripts/run_full_analysis.py FTP

2. SMTP
python3 scripts/run_full_analysis.py SMTP

3. RTSP
python3 scripts/run_full_analysis.py RTSP

4. HTTP
python3 scripts/run_full_analysis.py HTTP

输出物：
- data/outputs/evaluation_report_<project_id>.json
- data/outputs/protocol_schema_<project_id>.json
- data/outputs/generated_seeds_<project_id>.json
- data/outputs/feedback_report_<project_id>.json

## 5.3 运行四协议统一比较

python3 scripts/compare_protocols.py FTP SMTP RTSP HTTP

输出物：
- [data/outputs/multi_protocol_comparison.json](data/outputs/multi_protocol_comparison.json)

## 5.4 运行回归

python3 scripts/run_regression.py --rounds 3 --protocols FTP SMTP

输出物：
- [data/outputs/regression_report.json](data/outputs/regression_report.json)

## 5.5 导入 ProFuzzBench 数据

1. 本地目录导入
python3 scripts/fetch_profuzzbench_data.py --from-local <本地目录>

2. ZIP 下载导入
python3 scripts/fetch_profuzzbench_data.py --zip-url <zip链接>

## 5.6 测试 provider function calling

1. 单轮工具调用测试
python3 scripts/test_llm_single_turn_tools.py

2. 通用 function calling 测试
python3 scripts/test_llm_function_calling.py

3. 多轮 tool loop 兼容性测试
python3 scripts/test_llm_tool_loop.py

# 6. 当前实验与运行结果

说明：本节优先使用统一产物 [data/outputs/multi_protocol_comparison.json](data/outputs/multi_protocol_comparison.json) 与 [data/outputs/regression_report.json](data/outputs/regression_report.json)。若与旧报告有差异，以实际仓库输出为准。

## 6.1 四协议统一纯 Agent 模式结果

运行来源：
- compare 脚本 [scripts/compare_protocols.py](scripts/compare_protocols.py)
- 输出 [data/outputs/multi_protocol_comparison.json](data/outputs/multi_protocol_comparison.json)

| 协议 | 输入(doc/trace/seeds) | message types | states | transitions | probe runs | spec agent llm calls | trace agent llm calls | spec fallback | trace fallback | transition provenance(agent) | transition provenance(fallback) |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
| FTP | 1/10/39 | 39 | 8 | 14 | 3 | 1 | 1 | 否 | 否 | 14 | 0 |
| SMTP | 1/5/5 | 14 | 7 | 16 | 3 | 1 | 1 | 否 | 否 | 16 | 0 |
| RTSP | 1/3/3 | 7 | 6 | 2 | 2 | 1 | 1 | 否 | 否 | 2 | 0 |
| HTTP | 1/3/3 | 9 | 5 | 11 | 3 | 1 | 1 | 否 | 否 | 11 | 0 |

这些结果说明：
- 已实现并验证：四协议在同一 pipeline 下都可以 agent-first 跑通，且无 spec/trace fallback。
- 已有但待强化：RTSP/HTTP 的输入样本较少，导致状态与转移覆盖偏薄。
- 尚未完成：转移状态仍以 hypothesis 为主，supported 比例未建立优势。

## 6.2 稳定性回归结果

运行来源：
- 回归脚本 [scripts/run_regression.py](scripts/run_regression.py)
- 输出 [data/outputs/regression_report.json](data/outputs/regression_report.json)

FTP（3轮）：
- message_types: min 39, max 39, mean 39.0, stdev 0.0（稳定）
- states: min 8, max 8, mean 8.0, stdev 0.0（稳定）
- transitions: min 15, max 20, mean 17.67, stdev 2.517（波动）

SMTP（3轮）：
- message_types: min 12, max 12, mean 12.0, stdev 0.0（稳定）
- states: min 7, max 10, mean 8.0, stdev 1.732（波动）
- transitions: min 14, max 17, mean 15.0, stdev 1.732（波动）

解释：
- Spec Agent 更稳定：输入是相对固定的 doc/summary，输出结构受工具 schema 强约束，message_types 基本不抖动。
- Trace Agent 会波动：trace 到状态/转移的抽象仍受模型解释路径影响，尽管单轮工具调用已改善稳定性，仍存在轮次差异。
- 对课程作业结论的意义：系统已达到“可比较、可展示”的稳定下限，但应把“部分恢复、可解释原型”作为结论，而非“高精度完整恢复”。

## 6.3 当前结果总体判断

已经足够支撑课程项目的部分：
- 四协议统一 agent pipeline 可跑通。
- API/前端可以完整展示状态机、证据链、probe 历史和运行摘要。
- 统一 comparison/regression 产物可直接支撑实验章节。

仍是“可运行，待增强”的部分：
- transition supported 比例偏低。
- probe 对最终状态判定的增益还不稳定。
- RTSP/HTTP 样本规模仍小。

协议展示优先级建议：
- 主结果：FTP
- 次结果：SMTP
- 泛化补充：RTSP/HTTP

当前不适合作主结果的部分：
- 仅有 message/invariant、但无状态转移的数据点（如历史文件 [data/outputs/evaluation_report_31.json](data/outputs/evaluation_report_31.json) 这种输入为空的异常样例）

# 7. WebUI 展示设计与当前前端承接情况

前端总体定位：当前更像“结果展示页 + 轻量运行控制台”的组合，不是完整调度平台。

## 7.1 Dashboard 当前展示内容

页面实现： [frontend/src/pages/Dashboard.tsx](frontend/src/pages/Dashboard.tsx)

已展示：
- dashboard 基础统计（message/state/transition/invariant/probe/disputed）
- runtime 状态与 stage 标签
- artifact 摘要（schema_message_count、seed_count、feedback_action_count、focus_commands、unused_message_types）
- 推荐动作
- Agent Path Signals（spec/trace/probe llm calls、fallback、transition provenance、transition 状态分布）

## 7.2 runtime / analysis-summary 如何进入前端

前端 API 客户端定义在 [frontend/src/api/client.ts](frontend/src/api/client.ts)：
- getRuntime -> /projects/{id}/runtime
- getAnalysisSummary -> /projects/{id}/analysis-summary

后端聚合入口在 [backend/app/api/projects.py](backend/app/api/projects.py) 的 analysis_summary。

## 7.3 Agent Path Signals 是什么

字段模型在 [backend/app/schemas/protocol.py](backend/app/schemas/protocol.py) 的 AgentPathRead，主要包括：
- spec_fallback
- trace_fallback
- spec_llm_calls
- trace_llm_calls
- probe_llm_calls
- transition_provenance_agent/fallback/mixed
- probe_evidence_count
- llm_evidence_count
- transition_supported/hypothesis/disputed

前端展示在 Dashboard 的 AgentPathPanel。

## 7.4 状态机页如何展示状态和边

页面实现： [frontend/src/pages/StateMachine.tsx](frontend/src/pages/StateMachine.tsx)

特点：
- 基于 SVG 自绘节点和曲线边
- 边颜色按 status 区分（supported/disputed/hypothesis）
- 节点颜色支持跨协议命名映射 + hash fallback
- 点击边可打开 Drawer 查看 transition 证据

## 7.5 证据链页如何展示 evidence

页面实现： [frontend/src/pages/EvidenceChain.tsx](frontend/src/pages/EvidenceChain.tsx)

逻辑：
- 按 claim_type:claim_id 分组
- 结合 transition/invariant 显示 claim 文案与 status
- 每条 evidence 展示 source_type、source_ref、snippet、score

## 7.6 probe 历史页如何展示请求/响应与模型修正

页面实现： [frontend/src/pages/ProbeHistory.tsx](frontend/src/pages/ProbeHistory.tsx)

逻辑：
- 读取 ProbeRun.request_payload/response_payload/result_summary
- 双栏展示命令序列与交互回包
- 显示目标 host:port 与时间

## 7.7 多协议状态节点颜色适配

状态机页中已有 FTP/SMTP/RTSP/HTTP 的命名颜色映射与未知节点 hash 配色，便于多协议同页视觉区分（见 StateMachine COLORS 与 hashColor 逻辑）。

## 7.8 当前前端完成度判断

已完成并可展示：
- 五页联动（Dashboard/StateMachine/Messages/Evidence/Probes）
- 项目批次切换（ProjectContext + Header Select）
- runtime + analysis-summary 承接

仍缺但不影响课程展示：
- 更细粒度的实验对比组件（比如直接展示 regression 多轮曲线）
- 更丰富的 probe-to-claim 回溯可视化

# 8. 当前局限性

本节按“诚实口径”整理，不将计划写成结果。

- 当前系统明显更适合文本协议，不适合复杂二进制协议。
- probe 覆盖率仍有限，且对最终 supported 提升尚不显著。
- transition 的 supported 比例仍偏低，很多结果停留在 hypothesis。
- RTSP 数据量不足（doc/trace/seeds 仅 1/3/3 量级），导致转移数偏低。
- 四协议成熟度不均衡，FTP 最成熟，SMTP 次之，RTSP/HTTP 更偏泛化演示。
- 与 ProFuzzBench 全范围 benchmark 仍有明显差距；当前主要是样本复用与课程原型验证。
- 当前重点不是完整 benchmark 对抗，而是课程作业级原型闭环与可解释展示。

# 9. 当前项目阶段判断

基于代码和输出，当前阶段判断如下：

- 是否脱离原型早期阶段：是。已经从单点脚本验证进入到多协议统一 pipeline + API + 前端展示阶段。
- 是否进入可展示、可写作阶段：是。已有稳定的 comparison/regression/analysis-summary 产物链。
- 当前更接近单协议验证还是多协议课程项目平台：更接近“多协议课程项目平台（以 FTP 为主、其他协议补充）”。

为更稳支撑最终写作，仍建议收尾的代码项：
- 继续提升 trace 结果跨轮稳定性。
- 提升 probe 证据对 claim 状态的实际贡献。
- 对 RTSP/HTTP 补更多 trace/seeds，减少“仅泛化演示”的薄弱感。

# 10. 下一步最推荐的工程动作

以下是代码层面的执行建议，不是论文写作建议。

高优先级：
1. 固化四协议统一评估口径
- 在 compare/regression 里统一导出同一套指标字段，减少后处理口径分叉。
- 重点文件： [scripts/compare_protocols.py](scripts/compare_protocols.py)、[scripts/run_regression.py](scripts/run_regression.py)

2. 补强 probe 可验证性
- 增加 probe target 到 evidence 的闭环验证统计，避免 probe_runs 有值但证据增益低。
- 重点文件： [backend/app/services/probe_service.py](backend/app/services/probe_service.py)、[backend/app/api/projects.py](backend/app/api/projects.py)

3. 补强 RTSP/HTTP 结果
- 增加 sessions 与 seeds 样本，优先补状态关键路径。
- 重点目录： [data/traces/rtsp_sessions.txt](data/traces/rtsp_sessions.txt)、[data/traces/http_sessions.txt](data/traces/http_sessions.txt)、[data/traces/profuzzbench/rtsp](data/traces/profuzzbench/rtsp)、[data/traces/profuzzbench/http](data/traces/profuzzbench/http)

中优先级：
4. fallback 来源进一步细粒度可解释
- 继续细分 evidence/source_ref 标记，让 transition provenance 的 agent/fallback/mixed 更可审计。
- 重点文件： [backend/app/services/trace_agent_service.py](backend/app/services/trace_agent_service.py)、[backend/app/api/projects.py](backend/app/api/projects.py)

5. 连续回归继续补
- 从 3 轮扩到 5 轮，并保留协议子集（FTP/SMTP）与全协议模式两套报告。

6. WebUI 继续承接统一结果
- 在 Dashboard 增加 regression/comparison 视图入口，减少“只看单项目批次”的割裂感。

低优先级（有余力再做）：
7. 新增一个简单文本协议
- 可优先 SIP 或 POP3，复用现有 adapter 模板验证扩展成本。

# 11. 课程作业可交付性判断

明确结论：当前项目已经足以作为课程期末论文/项目提交基础。

为什么可以：
- 有完整工程链路：输入 -> agent pipeline -> artifact -> API -> WebUI。
- 有真实多协议结果：comparison 和 regression 文件可直接作为实验素材。
- 有可解释性：evidence 绑定、agent_path_signals、transition provenance 都已在后端定义并前端展示。
- 有运行可复现性：脚本入口齐全，且本地 probe 服务可启动。

什么条件下可以直接开始写作：
- 以 FTP 为主结果，SMTP 为次结果，RTSP/HTTP 做泛化补充。
- 明确写出“课程原型、agent-first、部分恢复、可解释”的边界。
- 用现有 JSON 报告作为表格和数据来源。

当前还缺的是“增强说服力”的内容，而不是“决定能否交付”的内容：
- 例如更高 probe 覆盖、更稳的 trace 跨轮表现、更丰富的 RTSP/HTTP 样本。

# 12. 可直接复用到正式论文/报告的素材清单

可直接复用到实验部分的表格：
- 四协议统一对比表（来自 [data/outputs/multi_protocol_comparison.json](data/outputs/multi_protocol_comparison.json) 的 comparison_table）
- FTP/SMTP 三轮稳定性表（来自 [data/outputs/regression_report.json](data/outputs/regression_report.json) 的 analyses 与 per_round）

可直接改写到方法部分的内容：
- 架构分层与调用链（见 [backend/app/services/pipeline_service.py](backend/app/services/pipeline_service.py)）
- ProtocolAdapter 抽象（见 [backend/app/protocols/base.py](backend/app/protocols/base.py)）
- 单轮 function calling 约束（见 [backend/app/core/llm_client.py](backend/app/core/llm_client.py)）
- Verifier 的混合校验机制（见 [backend/app/services/verifier_service.py](backend/app/services/verifier_service.py)）

可作为附录或补充材料的脚本与 artifact：
- 运行脚本： [scripts/run_full_analysis.py](scripts/run_full_analysis.py)、[scripts/compare_protocols.py](scripts/compare_protocols.py)、[scripts/run_regression.py](scripts/run_regression.py)
- 数据导入脚本： [scripts/fetch_profuzzbench_data.py](scripts/fetch_profuzzbench_data.py)
- provider 测试脚本： [scripts/test_llm_single_turn_tools.py](scripts/test_llm_single_turn_tools.py)、[scripts/test_llm_tool_loop.py](scripts/test_llm_tool_loop.py)
- 产物：evaluation_report/protocol_schema/generated_seeds/feedback_report/multi_protocol_comparison/regression_report

适合前端截图作为展示图的页面：
- Dashboard（运行状态、Agent Path Signals、Artifact Summary）
- State Machine（状态与边及证据抽屉）
- Evidence Chain（按 claim 聚合证据）
- Probe History（在线请求响应记录）

建议截图对应代码入口：
- [frontend/src/pages/Dashboard.tsx](frontend/src/pages/Dashboard.tsx)
- [frontend/src/pages/StateMachine.tsx](frontend/src/pages/StateMachine.tsx)
- [frontend/src/pages/EvidenceChain.tsx](frontend/src/pages/EvidenceChain.tsx)
- [frontend/src/pages/ProbeHistory.tsx](frontend/src/pages/ProbeHistory.tsx)

## 事实来源说明

本文主要依据以下真实仓库内容整理：
- Docs 文档： [Docs/protocol_analysis_coding_tasks.md](Docs/protocol_analysis_coding_tasks.md)、[Docs/multi_protocol_framework_blueprint.md](Docs/multi_protocol_framework_blueprint.md)、[README.md](README.md)
- 后端实现： [backend/app/services](backend/app/services)、[backend/app/protocols](backend/app/protocols)、[backend/app/api/projects.py](backend/app/api/projects.py)、[backend/app/core/llm_client.py](backend/app/core/llm_client.py)
- 运行脚本： [scripts/run_full_analysis.py](scripts/run_full_analysis.py)、[scripts/compare_protocols.py](scripts/compare_protocols.py)、[scripts/run_regression.py](scripts/run_regression.py)、[scripts/fetch_profuzzbench_data.py](scripts/fetch_profuzzbench_data.py)、[scripts/start_ftp_server.py](scripts/start_ftp_server.py)、[scripts/start_smtp_server.py](scripts/start_smtp_server.py)、[scripts/start_rtsp_server.py](scripts/start_rtsp_server.py)、[scripts/start_http_server.py](scripts/start_http_server.py)
- 前端实现： [frontend/src/pages](frontend/src/pages)、[frontend/src/api/client.ts](frontend/src/api/client.ts)
- 评估与对比产物： [data/outputs/multi_protocol_comparison.json](data/outputs/multi_protocol_comparison.json)、[data/outputs/regression_report.json](data/outputs/regression_report.json)、[data/outputs/evaluation_report_20.json](data/outputs/evaluation_report_20.json)、[data/outputs/evaluation_report_21.json](data/outputs/evaluation_report_21.json)、[data/outputs/evaluation_report_28.json](data/outputs/evaluation_report_28.json)、[data/outputs/evaluation_report_29.json](data/outputs/evaluation_report_29.json)

如个别 Docs 叙述与当前代码实现存在差异，以实际仓库代码和 data/outputs 当前文件内容为准。