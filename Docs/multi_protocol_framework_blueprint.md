# 多协议 ProFuzzBench 覆盖落地蓝图

## 一、文档目标

这份文档把“支持 FTP 并逐步覆盖 ProFuzzBench 协议集合”的目标落实成两部分：

- 一份可以直接执行的实事清单
- 一套与当前代码兼容、可渐进迁移的多协议框架设计

文档不假设推倒重来，而是明确区分：

- 当前已经可复用的通用层
- 当前硬编码为 FTP 的协议绑定层
- 从 FTP-only 演进到多协议平台的迁移路径

---

## 二、当前基线

截至 `evaluation_report_14.json`，仓库已经具备一条可运行的 FTP 端到端链路：

- Spec Agent
- Trace Agent
- Verifier Agent
- Probe Agent
- Protocol Schema Artifact
- Generated Seeds Artifact
- Feedback Artifact
- Pipeline Runtime / Stage Tracking
- WebUI 对 runtime 与 artifact 的展示基础

当前问题不在于缺少 agent 主流程，而在于协议适配层仍然几乎全部写死为 FTP。

在后续第一轮 adapter 化实现中，`evaluation_report_16.json` 已验证：`ProtocolAdapter` / `ProtocolRegistry` / `FTPProtocolAdapter` 骨架已经落地，且 Spec / Trace / Probe / artifact / runner 已能够通过 adapter 正常驱动 FTP 主链路。

在后续 Trace agent-first 稳定化中，`evaluation_report_20.json` 与 `evaluation_report_21.json` 已连续验证：Trace 改为单工具调用承载 `observations + final analysis` 后，`trace_agent` 可稳定保持工具主路径（`llm_tool_calls.trace_agent=1`，`fallback_used.trace_agent=False`），并维持 `message_types=39` 且无斜杠伪类型污染。

在最新自迭代中，评估报告已加入 `agent_path_signals` 与 `claim_provenance_distribution`，可直接观测 agent/fallback 贡献；`evaluation_report_28.json` 显示 `spec/trace/probe` 三阶段均成功 tool call，且 transition 来源为 `agent=21 fallback=0`。

### 当前可复用层

- `backend/app/services/pipeline_service.py`
- `backend/app/services/runtime_service.py`
- `backend/app/services/verifier_service.py`
- `backend/app/services/artifact_service.py` 的大部分通用导出逻辑
- `backend/app/core/llm_client.py`
- 数据模型、Evidence 体系、Project 体系、ProbeRun 体系

### 当前 FTP 绑定层

- `backend/app/tools/ftp_parser.py`
- `backend/app/tools/protocol_tools.py` 中的 FTP heuristics
- `backend/app/services/spec_agent_service.py` 中的 FTP prompt / trace summary 解析
- `backend/app/services/trace_agent_service.py` 中的 FTP prompt / parser / fallback
- `backend/app/services/probe_service.py` 中的 FTP probe execution 和命令生成
- `scripts/run_full_analysis.py` 中的 FTP 数据导入与项目初始化
- `scripts/start_ftp_server.py`

---

## 三、目标状态

目标不是给每个协议复制一套 FTP 代码，而是建立一套“协议适配器驱动”的统一分析平台。

更进一步，下一阶段架构目标应明确为：**agent 调用工具主导分析，协议规则只承担 fallback、约束与安全护栏职责**。

### 目标能力

- 同一条 pipeline 支持多协议切换
- 同一套 agent 服务支持 protocol-aware prompt 与 fallback
- agent 通过 function calling 主导 message extraction、state inference、transition hypothesis、probe planning 与迭代反馈决策
- tools 提供可验证、可复现、可审计的操作能力，而不是把协议结论预先写死在 service 中
- 每个协议通过 adapter 注入：parser、heuristics、probe、seed strategy、target bootstrap
- 统一导出 schema / seeds / feedback / runtime
- 统一 WebUI 展示，不因协议不同而改页面结构
- 新增协议时只需要补协议包，不需要改 agent 主干

### 非目标

- 一次性支持所有复杂二进制协议
- 一次性接通 ProFuzzBench 所有目标
- 一次性消除所有 hypothesis
- 一次性实现通用 PCAP 自动深度解析

---

## 四、完整框架设计

### 4.1 总体架构

```text
ProtocolProject
  -> ProtocolRegistry.resolve(project.protocol_name)
      -> ProtocolAdapter
          -> parser
          -> prompt_provider
          -> trace_heuristics
          -> probe_executor
          -> seed_strategy
          -> target_profile
          -> artifact_policy

Pipeline Orchestrator
  -> Spec Agent
  -> Trace Agent
  -> Verifier
  -> Probe Agent
  -> Artifact Builder
  -> Seed Generator
  -> Feedback Analyzer

All stages consume shared domain models:
  SessionTrace / MessageType / ProtocolState / Transition / Invariant / Evidence / ProbeRun
```

设计原则：

- `pipeline_service` 继续做编排，不承载协议细节
- agent service 继续做业务流程，不直接写死 FTP
- 协议差异全部下沉到 `ProtocolAdapter`
- agent 应主导分析决策，tool 负责提供结构化观察、执行与校验能力
- adapter 必须允许“agent-first + deterministic fallback”并存
- 规则层不再承担主要分析职责，只作为 provider 异常、工具失败、在线环境不可用时的兜底路径

### 3.1 agent-first 原则

下一阶段不再把 parser + heuristic transition table 视为主体分析器，而是把它们降级为 tool 与 fallback：

- agent 负责提出候选 message types、states、transitions、invariants、probe goals
- tool 负责执行：解析、计数、检索、在线探测、结构化评分、artifact 导出
- rule-based logic 只在以下情况接管：
  - LLM 未返回 tool calls
  - 外部 provider 不可用
  - probe 环境不可达
  - 某些安全约束要求不能让 agent 自由生成高风险操作

这意味着系统目标从“规则承重，agent 增强”切换为“agent 承重，tools 校验，规则兜底”。

### 4.2 核心抽象：ProtocolAdapter

建议新增目录：

```text
backend/app/protocols/
  base.py
  registry.py
  ftp/
    adapter.py
    parser.py
    prompts.py
    heuristics.py
    probe.py
    seeds.py
    targets.py
```

建议定义统一接口：

```python
class ProtocolAdapter(Protocol):
    name: str
    display_name: str

    def parse_session(self, raw_text: str) -> list[dict]: ...
    def parse_session_pairs(self, raw_text: str) -> list[dict]: ...

    def format_trace_summary(self, traces: list) -> str: ...
    def summarize_observed_messages(self, traces: list) -> str: ...

    def infer_candidate_states(self, sessions: list[list[dict]]) -> dict: ...
    def propose_transitions(self, states: list[dict], messages: list[dict]) -> dict: ...
    def normalize_transition(self, from_state: str, to_state: str, message_type: str) -> tuple[str, str, str]: ...

    def spec_system_prompt(self) -> str: ...
    def spec_user_context(self, docs_text: str, traces: list) -> str: ...

    def trace_system_prompt(self) -> str: ...
    def trace_user_context(self, sessions: list[list[dict]], mt_result: dict, heuristic_states: list[dict]) -> str: ...

    def select_probe_targets(self, transitions: list, invariants: list) -> list[dict]: ...
    def generate_probe_commands(self, target: dict) -> list[str]: ...
    def execute_probe(self, commands: list[str]) -> list[dict]: ...

    def generate_seed_corpus(self, project_id: int, session, schema: dict) -> dict | None: ...

    def create_project_metadata(self) -> dict: ...
    def load_trace_inputs(self, project_root: str) -> list[str]: ...
    def load_seed_inputs(self, project_root: str) -> list[str]: ...
```

对于 agent-first 方案，adapter 还应提供该协议的工具暴露策略：

```python
class ProtocolAdapter(Protocol):
    def spec_tools(self) -> list[dict]: ...
    def trace_tools(self) -> list[dict]: ...
    def verifier_tools(self) -> list[dict]: ...
    def probe_tools(self) -> list[dict]: ...
```

这样协议差异不仅体现为 prompt，也体现为 agent 可调用的工具集合。

### 4.3 Registry 层

新增 `ProtocolRegistry`：

- 根据 `ProtocolProject.protocol_name` 返回 adapter
- 提供默认协议集合
- 拒绝未知协议并返回明确错误

建议接口：

```python
class ProtocolRegistry:
    def register(self, adapter: ProtocolAdapter) -> None: ...
    def get(self, protocol_name: str) -> ProtocolAdapter: ...
    def list_supported(self) -> list[str]: ...
```

### 4.4 Agent 服务层改造目标

#### Spec Agent

保留：

- tool schema
- evidence 落库
- invariant / message type 落库

替换：

- FTP 专属 prompt
- FTP trace summary 构造
- FTP observed commands summary
- 解析函数入口

改造后：

```text
run_spec_agent(project_id, session)
  -> adapter = registry.get(project.protocol_name)
  -> docs = load docs
  -> traces = load traces
  -> user_message = adapter.spec_user_context(...)
  -> system_prompt = adapter.spec_system_prompt()
```

#### Trace Agent

保留：

- tool schema
- 状态与转移的落库逻辑
- heuristic augmentation 框架
- fallback 框架

替换：

- `parse_ftp_session`
- `parse_ftp_session_pairs`
- `infer_candidate_states`
- `propose_transitions`
- `TRACE_SYSTEM_PROMPT`
- `REIN` 这类 normalization 规则应移入 adapter

新增目标：

- 让 agent 优先通过工具获得 session statistics、message inventory、response pattern summary，再自行产出状态与转移
- heuristics 不再直接主导转移生成，而是作为 agent 的候选参考或 fallback 输出

#### Probe Agent

保留：

- ProbeRun 落库
- 结果回写模型
- LLM batch planning 框架

替换：

- FTP socket execution
- FTP probe command templates
- FTP target prioritization prompt

新增目标：

- agent 应主导选择“验证哪条 claim 最值钱”
- tool 应负责执行探测并回传 transcript / normalized result
- probe command template 只作为最低保底，而不是默认主路径

### 4.5 Artifact 层改造目标

`artifact_service.py` 中有两部分：

- 通用 artifact 逻辑
- FTP 特有 seed 生成逻辑

建议拆成：

- `artifact_service.py`
  - 负责通用 schema / feedback 计算
- `adapter.generate_seed_corpus(...)`
  - 负责协议专属 seed strategy

也可以保留当前函数名，但内部通过 adapter 分派。

### 4.6 Probe 执行层设计

Probe 层必须明确分为两层：

#### Planning

- 选择哪些 claim 需要 probe
- 用 LLM 或规则生成 probe plan

#### Execution

- 真正连服务端并执行协议交互

建议新增抽象：

```python
class ProbeExecutor(Protocol):
    def execute(self, commands: list[str], target_config: dict) -> list[dict]: ...
```

文本协议通常可按“request/response”执行；复杂协议可能需要：

- 多连接
- 二进制 framing
- 有状态 session token
- data channel / side channel

所以 execution 不能继续写死在 `probe_service.py`。

### 4.7 Target / Environment 层设计

要想真正扩大 ProFuzzBench 覆盖，需要一个 target 层。

建议新增：

```text
backend/app/protocols/<protocol>/targets.py
scripts/targets/
  start_ftp_target.py
  start_smtp_target.py
  start_http_target.py
```

统一目标描述：

```python
{
  "host": "127.0.0.1",
  "port": 2121,
  "transport": "tcp",
  "mode": "text",
  "startup_script": "scripts/targets/start_ftp_target.py",
  "healthcheck": {...}
}
```

### 4.8 Runtime / WebUI 兼容性要求

当前 runtime stage 已经通用，不应再按协议拆 stage。应扩展的是 stage summary。

建议每个 stage summary 增加：

- `protocol_name`
- `adapter_name`
- `fallback_used`
- `parsed_session_count`
- `probe_transport`
- `target_profile`

WebUI 不需要按协议重写页面，但需要支持：

- 不同协议的 message template 展示
- 不同协议的 probe transcript 展示
- 不同协议的状态命名差异

---

## 五、目录结构建议

```text
backend/
  app/
    protocols/
      base.py
      registry.py
      ftp/
        adapter.py
        parser.py
        prompts.py
        heuristics.py
        probe.py
        seeds.py
        targets.py
      smtp/
        adapter.py
        parser.py
        prompts.py
        heuristics.py
        probe.py
        seeds.py
        targets.py
      http/
        adapter.py
        parser.py
        prompts.py
        heuristics.py
        probe.py
        seeds.py
        targets.py
    services/
      pipeline_service.py
      runtime_service.py
      spec_agent_service.py
      trace_agent_service.py
      verifier_service.py
      probe_service.py
      artifact_service.py
    tools/
      generic_protocol_tools.py
scripts/
  run_full_analysis.py
  targets/
    start_ftp_target.py
    start_smtp_target.py
    start_http_target.py
Docs/
  protocol_analysis_coding_tasks.md
  multi_protocol_framework_blueprint.md
```

说明：

- `tools/protocol_tools.py` 未来应弱化为通用工具集合
- 协议 heuristics 不再放在全局 tools 中
- FTP 不再作为系统默认写死逻辑，而是第一个 adapter 实现

---

## 六、实事清单

下面不是愿景，而是建议直接照着排期执行的落地任务。

### Phase 0：冻结 FTP 基线

目标：在继续架构演进前，保住当前 FTP 能力。

任务：

- 固化 `evaluation_report_14.json` 为迁移前基线
- 给 FTP parser、trace heuristics、probe 关键路径补回归测试
- 明确迁移期间必须保持的 KPI：
  - `unused_message_types == []`
  - `isolated_states == []`
  - `REIN -> RESETTING` 语义不回退

验收标准：

- FTP baseline 测试稳定可重复
- 新架构接入前后，FTP 关键指标无明显回退

### Phase 1：抽出 ProtocolAdapter 骨架

目标：在不改变行为的前提下，把 FTP 写死逻辑抽成 adapter。

任务：

- 新增 `protocols/base.py`
- 新增 `protocols/registry.py`
- 新增 `protocols/ftp/adapter.py`
- 把 parser、prompt、heuristics、probe 入口封装到 FTP adapter
- 在 `pipeline_service` 或 agent service 中通过 `protocol_name` 获取 adapter

验收标准：

- FTP full pipeline 仍然可跑
- `spec_agent_service.py` / `trace_agent_service.py` / `probe_service.py` 不再直接 import `ftp_parser.py`
- prompt 中不再硬编码 FTP 文案，而是从 adapter 读取

### Phase 1.5：把 service 从 rule-first 改成 agent-first

目标：让 agent 真正主导分析，rules 降级为 fallback。

任务：

- 在 Spec / Trace / Probe 中重构 tool schema，使 agent 可以先调工具获取结构化观察，再生成结论
- 将现有 heuristic 结果从“默认落盘来源”改为“候选参考输入”
- 保留 deterministic fallback，但只在 tool 调用失败或 provider 失败时触发
- 为每个阶段记录“agent output”和“fallback output”的来源标签，便于 WebUI 区分

验收标准：

- 正常运行路径中，状态与转移的主要创建来源是 agent tool call，而不是 fallback
- `fallback_used` 只在异常路径出现
- evaluation 报告中可区分 agent-derived 与 fallback-derived claim

### Phase 2：让 pipeline 参数化协议

目标：同一套脚本支持多协议入口。

任务：

- 改造 `scripts/run_full_analysis.py`，支持 `protocol_name`
- 为不同协议选择不同 trace / seed 目录
- project 创建逻辑不再固定 `protocol_name="FTP"`
- API 层返回 supported protocols 列表

验收标准：

- 不改代码，只改参数即可切协议
- 对未知协议给出清晰错误

### Phase 3：抽出 ProbeExecutor 与 TargetProfile

目标：把在线验证做成可替换组件。

任务：

- 将 FTP socket 执行逻辑从 `probe_service.py` 下沉到 `protocols/ftp/probe.py`
- 为 probe executor 定义统一返回格式
- 新增 target profile 概念
- 脚本层支持 protocol-specific target startup

验收标准：

- `probe_service.py` 不再直接实现 FTP 交互细节
- ProbeRun 结构保持兼容

### Phase 4：接入第二个文本协议

目标：证明架构不是只对 FTP 成立。

推荐第二协议：`SMTP` 或 `HTTP`。

任务：

- 新增协议 parser
- 新增 prompt provider
- 新增 heuristics
- 新增 probe executor
- 新增 target 启动脚本
- 新增最小 trace / seed 样本

验收标准：

- 第二协议能跑通 full pipeline
- 能产出 schema / seeds / feedback
- 不需要修改 FTP adapter 才能工作
- 第二协议接入时，agent 工具调用仍是主分析路径，而不是重新复制一套规则表

### Phase 5：建立协议接入模板

目标：后续接新协议时只按模板填空。

任务：

- 定义 `new_protocol_adapter_checklist.md`
- 给出最小接入模板
- 固化 per-protocol 测试模板

验收标准：

- 新协议接入步骤可复制
- 不需要重新讨论目录结构和接口设计

### Phase 6：逐步扩展 ProFuzzBench 覆盖

目标：按优先级接入更多目标，而不是一次性全开。

建议优先顺序：

- 文本命令型协议
- 半结构化协议
- 最后处理二进制或强 framing 协议

验收标准：

- 每新增一个协议，都形成独立 baseline report
- 每个协议都满足最小 DoD

---

## 七、每阶段 Definition of Done

### FTP adapter 化完成的 DoD

- FTP 全流程仍然可运行
- `evaluation_report_14` 级别指标无显著回退
- 所有 FTP 绑定逻辑都可通过 adapter 访问

### 新协议最小接入 DoD

- 有 parser
- 有 trace fallback
- 有 prompt provider
- 有 probe executor
- 有 target startup
- 有最小样本 traces / seeds
- 能产出三类 artifact
- 有至少一份 evaluation report

### “支持某协议” 的严格 DoD

- full pipeline 跑通
- 无大面积伪 message type
- `unused_message_types` 不长期失控
- `isolated_states` 不长期失控
- 至少有一部分关键转移被 probe 支撑
- WebUI 可以展示其 runtime / artifact / probe history

---

## 八、迁移顺序建议

建议严格按下面顺序做，避免一边抽象一边失去当前可运行能力。

1. 冻结 FTP baseline
2. 抽出 adapter 接口，但 FTP 行为不变
3. 把 parser / prompt / heuristics / probe 从 service 中搬出
4. 让 `run_full_analysis.py` 接受协议参数
5. 接入第二协议验证抽象正确性
6. 再逐个扩展 ProFuzzBench 目标

禁止事项：

- 不要先大规模重写 domain model
- 不要先做二进制协议再验证 adapter 设计
- 不要让 WebUI 绑定协议名写死逻辑
- 不要在没有 target bootstrap 的情况下声称“已支持协议”

---

## 九、风险清单

### 风险 1：抽象过早，FTP 回退

规避：

- Phase 0 先补 FTP baseline tests
- 每个阶段都回跑 FTP report

### 风险 2：adapter 设计过于理想化

规避：

- 第二协议必须尽快接入验证
- 不用一次性设计覆盖所有二进制协议细节

### 风险 3：Probe 层仍然绑死文本协议

规避：

- 提前抽出 `ProbeExecutor`
- 统一 execution transcript 格式，而不是统一 transport

### 风险 4：artifact 层继续偷偷依赖 FTP 语义

规避：

- seed generation 明确由 adapter 驱动
- artifact_service 只保留通用计算和导出

---

## 十、建议的近期执行顺序

如果按最短路径推进，建议未来 3 个迭代按下面做：

### Iteration A

- 抽 `ProtocolAdapter`
- 抽 `ProtocolRegistry`
- 把 FTP parser / prompt / heuristics / probe 接到 adapter
- 把 Spec / Trace / Probe 改造成 agent-first tool orchestration

### Iteration B

- 参数化 `run_full_analysis.py`
- 引入 `TargetProfile`
- 抽 `ProbeExecutor`

### Iteration C

- 接入第二个文本协议
- 建立协议接入模板
- 固化多协议 baseline 报告机制

---

## 十一、下一步建议

当前最值得优先执行的不是继续优化 FTP 细节，而是：

- 先完成 `Phase 1 + Phase 1.5 + Phase 2`
- 把系统从“FTP 项目 + 规则主体”变成“支持协议注册的 agent-first 项目”

只有这一步完成，后续覆盖 ProFuzzBench 才不是重复堆特判。
