# Coding Agent 开发任务拆解

## 一、项目目标

实现一个面向通用网络协议的协议分析系统原型，支持 FTP、SMTP 等文本协议，融合多智能体、function calling、证据绑定、在线探测和 WebUI 可视化。

项目目标不是重写现有 ChatAFL 或 ProtocolGPT，而是实现一个新的通用协议分析平台，重点在于：

- 多源输入协议知识抽取
- 多智能体协作分析
- 证据绑定的协议模型构建
- 在线探测驱动的模型修正
- WebUI 展示状态机与证据链

---

## 当前实施进展（2026-04-25）

当前仓库内已经打通一条可运行的 FTP 协议分析流程，采用 ProFuzzBench FTP seeds、本地 `pyftpdlib` FTP 服务，以及单轮批量 function calling 的多 Agent 分析链路。

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
- 评估结果已更新导出到 `data/outputs/evaluation_report_6.json`

### 当前推荐运行方式

先启动本地 FTP 服务：

```bash
python3 scripts/start_ftp_server.py
```

再执行完整分析流程：

```bash
python3 scripts/run_full_analysis.py
```

如果只想验证 provider 的 function calling 能力，使用：

```bash
python3 scripts/test_llm_single_turn_tools.py
```

### 当前评估结果摘要

基于 1 份 FTP 文档、10 条本地 FTP 会话、39 条 ProFuzzBench seeds 的一次完整运行，得到：

- Message types: `41`
- States: `6`
- Transitions: `11`
- Invariants: `10`
- Evidence records: `71`
- Probe runs: `3`
- Transition status 分布：`supported=11`，`hypothesis=0`，`disputed=0`
- Invariant status 分布：`supported=10`，`hypothesis=0`，`disputed=0`
- Fallback 使用情况：`Spec=False`，`Trace=False`

### 当前 function calling 约束与实现策略

当前 provider 的 OpenAI-compatible 接口支持单轮 function calling，但在多轮 tool continuation 场景下会触发缺失 `thought_signature` 的服务端错误。因此当前实现采用以下策略：

- `llm_client.py` 使用单轮请求，不做多轮 tool continuation
- `tool_choice` 使用 `required`
- Spec Agent 改为一次性返回 `message_types[]`、`ordering_rules[]`、`field_constraints[]`
- Trace Agent 改为一次性返回 `states[]`、`transitions[]`、`observed_message_types[]`
- SDK 默认重试已关闭，便于快速暴露真实报错

这意味着当前方案优先保证稳定性与可跑通性，而不是依赖 provider 的多轮 tool loop 行为。

### 当前已知限制

- Verifier / Probe 虽已具备单轮批量 LLM 辅助，但目前仍保留强规则回退逻辑，属于混合模式而非纯 LLM 模式
- 部分非常规命令（如 `CAPI`、`PRUE`）目前只能做“消息类型识别”，尚未建立稳定的状态语义
- 当前 `supported` 结果偏多，后续可继续细化 Verifier 的保守性阈值，避免过度确认
- 当前更适合 FTP 这类文本协议；对复杂二进制协议仍需额外解析层支持

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

- 协议对象：FTP
- 输入来源：文档摘要、trace、在线交互日志
- 智能体：Spec Agent、Trace Agent、Verifier Agent、Probe Agent
- 可选暂缓：Code Agent
- 前端页面：总览页、状态机页、证据链页、Probe 历史页

不要求：

- 支持复杂二进制协议
- 大规模 fuzzing
- 完整 RFC 自动解析
- 全自动高精度状态机恢复

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

### 验收标准
- 能导出实验结果 JSON
- 能生成简单图表或 CSV

---

## 六、开发优先级

### P0
- 项目初始化
- 数据模型
- FTP parser
- 工具调用层
- Spec Agent
- Trace Agent
- Verifier Agent
- 基础 API

### P1
- Probe Agent
- 协议模型版本管理
- Dashboard
- 状态机视图
- 证据链视图

### P2
- Code Agent
- SMTP 支持
- 更完整的实验与统计输出
- 复杂 trace 导入

---

## 七、建议迭代计划

### 第 1 周
- 完成工程初始化
- 完成数据库模型
- 完成 FTP parser

### 第 2 周
- 完成工具调用层
- 完成 Spec Agent 和 Trace Agent
- 打通基础 API

### 第 3 周
- 完成 Verifier Agent
- 完成协议模型管理器
- 完成 dashboard 与状态图页

### 第 4 周
- 完成 Probe Agent 和在线执行器
- 完成证据链和 probe 历史页
- 打通端到端流程

### 第 5 周
- 增加实验统计和导出能力
- 做消融开关
- 修 UI 和演示细节

---

## 八、最低验收标准

项目至少需要满足以下条件：

1. 支持 FTP 样例协议
2. 能导入文档摘要和 trace 样本
3. 能输出消息类型、候选状态、候选转移
4. 每条 transition 至少可绑定证据
5. 能通过 probe 修正至少一条结论
6. WebUI 可展示状态图与证据链
7. 可以导出完整分析结果 JSON

---

## 九、附加建议

### 关于模型调用
- 不要让模型自由生成最终报告
- 强制使用 function calling / JSON schema
- 对关键输出做 schema 校验

### 关于协议范围
- 第一版只做 FTP
- 第二版再加 SMTP
- HTTP 放在扩展实验里做简化子集

### 关于展示
- 优先把状态图和证据链做漂亮
- probe 历史页对答辩展示很重要
- UI 里最好能展示“这条边为什么存在”

### 关于代码质量
- 核心工具函数写单元测试
- 所有 agent 输出落盘为 JSON artifact
- 所有流程保留可复现日志

---

## 十、最终交付清单

coding agent 最终需要交付：

- 可运行的前后端项目
- demo 数据集
- 本地启动脚本
- `.env.example`
- API 文档
- 端到端演示说明
- 实验导出样例
- 完整 README
