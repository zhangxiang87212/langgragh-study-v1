# Mini Research Agent：第十二阶段

当前阶段增加 Checkpoint 时间旅行与人工修正：可以查看历史状态，从任意历史
Checkpoint 创建独立线程分支，修改研究计划、删除错误资料或补充人工证据，并从
修正点之后继续执行。原线程不会被修改，修正点之前已经完成的昂贵节点也不会重跑。

第十一阶段为所有付费模型节点增加的容错和成本控制继续保留。LangGraph 的节点级
`RetryPolicy` 负责瞬时故障重试和指数退避；调用包装器负责同步 Provider 的超时；
持久化的用量事件与预算路由负责在开始下一批付费调用前停止工作流。第十阶段的
动态 Map-Reduce、流式日志、人工审批和 SQLite 跨进程恢复继续保留。

- Planner：使用结构化输出生成 3 到 6 个研究任务。
- Plan Approval：暂停 Graph，让用户确认或替换研究计划。
- Researcher：调用 Responses API 的 `web_search` 工具，汇总资料和来源 URL。
- Research Evaluator：评估任务覆盖度、来源质量、时效性和证据充分度。
- Writer：根据资料生成 Markdown 报告，并在循环中接收审核意见。
- Reviewer：使用结构化输出返回 0 到 100 分和修改意见。

当前工作流为：

```text
START → planner → plan_approval → prepare_research
                         ↑                │
                  Command(resume)         │ Send × N
                         ↑                ↓
                    用户确认/修改    ┌─ research_worker(task 1) ─┐
                                    ├─ research_worker(task 2) ─┤
                                    └─ research_worker(task N) ─┘
                                                   ↓
                                           research_reducer
                                                   ↓
                                      research_evaluator
                                          │          │
                                      资料不足      资料足够
                                          │          ↓
                                          └──→ prepare_research
                                                     writer → reviewer
                                                        ↑          ├─ 通过 → END
                                                        └──────────┤ 未通过
```

所有可能产生费用的路径之前都有预算检查。预算不足时不再调用模型，而是进入
`budget_exhausted` 生成一份明确标注“提前结束”的结果，然后前往 `END`。

## 容错与指数退避

`build_graph()` 为 Planner、Research Worker、Research Evaluator、Writer 和
Reviewer 配置同一份 LangGraph `RetryPolicy`：

```python
builder.add_node(
    "research_worker",
    research_worker_node,
    retry_policy=resilience.retry_policy(),
)
```

一次节点尝试遇到以下瞬时错误时会自动重试：连接失败、Provider 超时、限流、
HTTP 408/409/429 和 5xx。参数错误、数据校验错误等永久错误不会重试，避免重复
发送一个注定失败的请求。默认最多尝试 3 次，等待约为 1 秒、2 秒，并加入随机
抖动；间隔最大不超过 30 秒。

同步 OpenAI/DeepSeek SDK 调用由 `call_with_timeout()` 放入工作线程，并使用
`future.result(timeout=...)` 设置调用方截止时间。超时会抛出 LangGraph
`NodeTimeoutError` 的子类，因此仍可由同一份 `RetryPolicy` 处理。新线程会显式
复制 `contextvars`，保证 Writer token 和 Researcher 自定义事件仍能写入当前
LangGraph stream。

这里的截止时间能让 Graph 及时失败，但 Python 无法强行终止已经进入网络库的
线程；底层请求可能继续到 SDK 自身返回。因此生产部署还应让反向代理和 Provider
SDK 的网络超时不大于 `LLM_NODE_TIMEOUT_SECONDS`。

重试耗尽后，异常会离开当前节点。Checkpoint 保留最近一次成功 superstep；修复
外部故障后执行 `resume --thread-id ...`，LangGraph 只会重新调度快照中的待执行
节点，不重跑已经提交的上游节点。官方原理说明见
[LangGraph Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)。

## 用量与预算

每个成功的模型节点返回一个 `UsageEvent`。`usage_events` 使用 `operator.add`
Reducer，所以多个并行 Research Worker 的用量可以安全合并，并随 Checkpoint
一起保存。事件记录 LLM 调用数、搜索调用数、输入/输出 Token 和费用。

当前 OpenAI Responses 与 DeepSeek Responses/Chat 接口返回的用量结构并不完全
一致，所以本阶段统一采用透明估算：`ceil(文本字符数 / 3)`。报告和控制台都明确
标为“估算”。费用由估算 Token 乘以 `.env` 中用户配置的每百万 Token 单价得到；
单价为 0 时只统计 Token，不产生虚假的费用数字。

预算路由在下一步执行前调用 `budget_exceeded_reason()`：

- 并行研究开始前，一次性预留计划任务数对应的 LLM 调用额度。
- Evaluator、Writer、Reviewer 和重写开始前，各预留 1 次调用额度。
- 已达到 Token 或费用上限时，不再启动下一个付费节点。
- `SEARCH_MAX_ROUNDS` 控制最多进行几轮并行搜索。

Token 和费用只能在响应完成后得知，因此单次调用可能让累计值略微越过上限；保护
会阻止下一次调用。`LLM_MAX_CALLS` 是成功提交到 State 的逻辑调用数，LangGraph
内部因瞬时错误产生的失败重试不会写入 State，用量应再与 Provider 账单核对。

相关配置如下：

```dotenv
LLM_RETRY_MAX_ATTEMPTS=3
LLM_RETRY_INITIAL_INTERVAL=1
LLM_RETRY_BACKOFF_FACTOR=2
LLM_RETRY_MAX_INTERVAL=30
LLM_NODE_TIMEOUT_SECONDS=120

LLM_MAX_CALLS=30
SEARCH_MAX_ROUNDS=3
LLM_MAX_TOTAL_TOKENS=0
LLM_MAX_COST_USD=0
LLM_INPUT_COST_PER_MILLION=0
LLM_OUTPUT_COST_PER_MILLION=0
```

Token、费用上限和单价配置为 `0` 表示不启用对应限制。运行中的配置会复制进
初始 State，所以暂停后修改 `.env` 不会悄悄改变该任务原有预算。

## 幂等结果写入

结果文件名由稳定的 `run_id` 决定：

```text
outputs/research-report-{run_id}.md
```

`save_result()` 先写同目录临时文件，再用原子 `replace()` 提交。相同 run 恢复后
如果目标文件已经存在，会直接返回原路径，不会生成第二份报告，也不会覆盖已提交
内容。LLM 节点只返回 State 更新，不在节点内部写最终文件。

## 动态 Map-Reduce

`prepare_research` 每轮只执行一次，用来增加 `research_iteration`。它的条件边
根据计划动态返回多个 `Send`：

```python
return [
    Send(
        "research_worker",
        {
            "task": task,
            "task_index": task_index,
            "research_iteration": state["research_iteration"],
            ...
        },
    )
    for task_index, task in enumerate(state["plan"])
]
```

计划可能有 3 到 6 项，所以 Graph 在编译时并不知道 Worker 数量。每个 `Send`
都给同一个节点传入不同的 `ResearchWorkerState`，一个 Worker 只搜索一项任务。

多个 Worker 会同时更新 `research_results`。普通 State 字段遇到并行写入会冲突，
所以该字段使用 `operator.add` Reducer：

```python
research_results: Annotated[list[ResearchTaskResult], operator.add]
```

并行分支的完成顺序不稳定。每条结果都携带 `task_index`，Reducer 合并前会排序，
确保最终资料始终与人工批准的计划顺序一致。结果还携带 `run_id` 和
`research_iteration`，因此第二轮补充搜索或同一线程中的历史结果不会混入当前轮。
一个新 run 的第 1 轮会明确忽略历史正文和来源；只有本次 run 的第 2、3 轮才累积
上一轮资料和 Evaluator 意见。

`research_reducer` 完成 fan-in，负责：

- 选择当前 `run_id`、当前研究轮次的 Worker 结果。
- 按 `task_index` 排序并生成分任务 Markdown。
- 累积上一轮研究资料。
- 汇总并去重来源 URL。
- 把完整资料交给 Research Evaluator。

并发上限由 `create_run_config()` 设置：

```python
{
    "configurable": {"thread_id": thread_id},
    "max_concurrency": 4,
}
```

即使计划有 6 项，也最多同时运行 4 个调用，减少触发 Provider 限流的风险。

## LangGraph 流式执行

CLI 使用两种 stream mode：

```python
for part in graph.stream(
    graph_input,
    config=config,
    stream_mode=["updates", "custom"],
    version="v2",
):
    ...
```

- `updates`：节点完成后返回这个节点对 State 的局部更新。并行阶段会分别产生多个
  `research_worker` 更新。CLI 只打印节点名称，
  不把整个 State 和最终报告重复输出到控制台。
- `custom`：节点主动发出的自定义事件。当前用于 Writer token，以及每个
  Research Worker 的开始和完整搜索结果。

项目直接使用 OpenAI Python SDK，而不是 LangChain ChatModel，所以不能依赖
`messages` 模式自动捕获 token。`writer_node()` 通过 `get_stream_writer()` 获取
LangGraph 的事件写入器，再把回调交给 LLM Provider：

```python
def send_token(token: str) -> None:
    stream_writer(
        {"event": "llm_token", "node": "Writer", "text": token}
    )
```

OpenAI Writer 遍历 Responses API 的 `response.output_text.delta`；DeepSeek Writer
遍历 Chat Completions 的 `choices[0].delta.content`。每个 token 一方面立即写入
LangGraph 自定义流，另一方面累积成完整 `draft`，因此流式显示不会改变 State。

结构化输出仍在完整响应到达后统一校验。Planner、Research Evaluator 和 Reviewer
的结果较短，继续以完整日志显示；Researcher 在搜索完成后显示资料和来源。

## 持久化暂停和恢复

`plan_approval_node()` 通过 `interrupt()` 把研究计划交给调用方：

```python
decision = interrupt(
    {
        "question": "请确认研究计划后再继续。",
        "plan": state["plan"],
    }
)
```

第一次 `graph.stream()` 不会执行 Researcher，而是产生一个名为
`__interrupt__` 的 update。此时 SQLite 已经保存 Planner 的输出、待执行节点和
中断信息，所以第一个 Python 进程可以安全结束。

另一个 Python 进程打开相同的数据库后，使用相同的 `thread_id` 恢复：

```python
events = graph.stream(
    Command(resume={"action": "approve"}),
    config=config,
    stream_mode=["updates", "custom"],
    version="v2",
)
```

`Command(resume=...)` 中的值会成为 `interrupt()` 的返回值。如果用户修改计划，
确认节点会先更新 State 中的 `plan`，Researcher 使用的就是人工确认后的版本。

## 资料充分性循环

Research Evaluator 使用结构化输出返回 `research_score` 和
`research_comment`。`research_router()` 根据评分和当前研究轮数选择下一步：

- 评分大于或等于 80：资料足够，进入 Writer。
- 评分小于 80：把已有资料和评估意见交回 Researcher，做定向补充搜索。
- 连续 3 轮仍不足：为了避免无限循环和费用失控，停止搜索并进入 Writer。

补充搜索不会覆盖前一轮结果。Researcher 会累积研究内容，并对来源 URL
去重。最终文件会记录研究评分、评估意见和实际研究轮数。

单元测试中的默认 Graph 仍使用 `InMemorySaver`，让测试彼此隔离：

```python
graph = build_graph(checkpointer=InMemorySaver())
```

CLI 使用 `app/checkpoints.py` 创建 Checkpointer。默认后端是 `SqliteSaver`，
数据库位于 `checkpoints/research.sqlite`：

```python
with SqliteSaver.from_conn_string(database_path) as checkpointer:
    checkpointer.setup()
    graph = build_graph(checkpointer=checkpointer)
```

每次执行 Graph 时都需要传入线程配置：

```python
config = {"configurable": {"thread_id": "user-001"}}
events = graph.stream(initial_state, config=config, stream_mode="updates")
```

`thread_id` 不是 State 字段。它是 Checkpointer 用来区分不同执行线程的键。
两个不同的 `thread_id` 会保存两组独立的 State 和历史快照。

```python
snapshot = graph.get_state(config)
history = list(graph.get_state_history(config))
```

`snapshot.values` 是当前快照中的 State，`snapshot.next` 是接下来要执行的节点。
工作流正常结束后，`snapshot.next` 是空元组。

SQLite 适合当前的单机同步 CLI。将来部署多个 Worker 时，应继续替换为
PostgreSQL Checkpointer，而不是让多个进程长期共享一个 SQLite 连接。

## Checkpoint 配置

`.env` 支持两项独立于 LLM Provider 的配置：

```dotenv
CHECKPOINT_BACKEND=sqlite
CHECKPOINT_DB_PATH=checkpoints/research.sqlite
```

`CHECKPOINT_BACKEND` 可设为：

- `sqlite`：默认值，程序退出后仍保留状态。
- `memory`：只在当前进程保存状态，适合临时实验。

数据库属于运行数据，`checkpoints/` 已加入 `.gitignore`，不会提交到 Git。

Researcher 会把两类数据写入 State：

- `research_content`：模型根据搜索结果整理的中文研究资料。
- `sources`：从 Web Search 工具调用中提取并去重的来源 URL。

搜索被设置为 `required`，避免模型跳过工具直接凭记忆回答。并行化会增加调用量：
计划有 3 到 6 项时，每轮会产生 3 到 6 次 Researcher Responses 请求，最多三轮
时累计 9 到 18 次请求；如果首轮通过则只有 3 到 6 次。OpenAI 每个请求最多允许
6 次 Web Search 工具调用，所以
极端理论上限是 108 次工具调用。DeepSeek 会忽略 `max_tool_calls`，仍由 Graph 的
研究轮数和每轮 Worker 数量限制外层 Responses 请求。真实费用与计划长度、资料
评分、模型是否使用多次搜索有关，运行前应确认额度。

Reviewer 返回评分后，`review_router()` 只负责做出选择：

- 评分大于或等于 80，返回 `pass`，工作流前往 `END`。
- 评分小于 80 且重写少于 3 次，返回 `rewrite`，工作流回到 `writer`。
- 已重写 3 次仍未通过，也返回 `pass`，强制结束工作流。

这里的 `pass` 表示“走向结束节点”，不一定表示报告质量合格。最终调用方仍应
检查 `review_score`，区分“审核通过”和“达到重写上限后结束”。

`revision_count` 的计数规则很简单：首次生成报告时是 0；每次收到审核意见并
回到 Writer 时加 1。`MAX_REVISIONS` 统一定义在 `app/graph.py` 中。

## 运行项目

建议使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

### Web 页面运行方式

Web 用户不需要在 `.env` 中配置 LLM Provider 或 API Key。先启动后端：

```bash
uvicorn app.server:app --reload --port 8011
```

再启动前端：

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。首次进入时会自动打开“模型连接设置”，用户可以选择
OpenAI 或 DeepSeek，并填写自己的 API Key 和模型名。保存后才能创建或恢复会产生
LLM 调用的研究任务；页面顶部的模型状态可以随时重新打开设置或清除密钥。

页面提交的 API Key 只保存在 FastAPI 进程的会话内存中：

- 浏览器只接收一个 `HttpOnly`、`SameSite=Strict` 的随机会话 Cookie。
- API Key 不会写入 localStorage、SQLite、Checkpoint、报告或应用日志。
- 不同浏览器会话的配置互相隔离，会话最长 12 小时。
- 后端进程重启后所有页面密钥立即清除，需要重新填写。
- 公网部署必须使用 HTTPS，否则传输中的 API Key 无法得到 TLS 保护。

如果前端和 API 跨 Origin 部署，需要在 `.env` 中显式配置允许的前端地址：

```dotenv
CORS_ALLOWED_ORIGINS=https://research.example.com
LLM_SESSION_COOKIE_SECURE=true
```

服务端不再使用允许凭据的通配符 CORS。生产环境建议通过同一域名反向代理
`/api`，并限制受信任的 Origin。

当前会话密钥存储在单个 Python 进程内，适合本地运行和单 Worker 部署。使用多个
Uvicorn/Gunicorn Worker 时，需要改成带 TTL 的共享秘密存储并配置用户认证，或者
使用会话粘滞；否则同一浏览器的后续请求可能落到没有该配置的 Worker。项目现有的
研究线程接口还不是用户级数据隔离系统，直接部署为公共 SaaS 前必须补充登录鉴权和
线程所有权校验。

### CLI 运行方式

命令行模式仍然支持 `.env`，方便本地学习和自动化脚本。使用 OpenAI：

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5-nano
OPENAI_SEARCH_MODEL=gpt-5.4-mini
```

使用 DeepSeek 作为主模型：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

`LLM_PROVIDER` 支持 `openai` 和 `deepseek`。切换为 DeepSeek 后，Planner、
Researcher、Research Evaluator、Writer 和 Reviewer 全部使用 DeepSeek。
Researcher 通过 DeepSeek 的 Responses API 调用服务端 `web_search`，不再需要
OpenAI API Key。两个 Provider 都使用同一份研究 Prompt，来源会从
搜索元数据、引用标注或正文 URL 中提取并去重。

`.env` 已被 Git 忽略。不要把任何真实 API Key 写入 `.env.example`、前端源码或
提交到代码仓库。

创建一个新任务：

```bash
python -m app.main run
```

也可以在命令后传入自己的主题：

```bash
python -m app.main run "研究 AI Agent 在教育领域的应用趋势"
```

指定一个 Checkpoint 线程：

```bash
python -m app.main run "研究 AI Agent 在教育领域的应用趋势" --thread-id user-001
```

如果不传 `--thread-id`，程序会生成一个 UUID，并把它记录到控制台。Planner
输出计划后，程序会在审批点停止。此时可以关闭程序，再执行：

```bash
python -m app.main resume --thread-id user-001 --approve
```

如果需要替换研究计划：

```bash
python -m app.main resume --thread-id user-001 \
  --plan "研究官方文档；查找生产案例；总结风险"
```

审批恢复会从 `plan_approval` 继续，不会再次执行 Planner。任务完成后，最终报告
仍然写入 `outputs/`。

如果某个普通节点因为网络或 API 错误而失败，修复问题后不需要审批参数：

```bash
python -m app.main resume --thread-id user-001
```

Graph 会从快照记录的待执行节点继续。已经成功完成并写入 Checkpoint 的上游节点
不会重复执行。

只读查看任务状态，不会调用 LLM：

```bash
python -m app.main status --thread-id user-001
```

按执行顺序查看全部 Checkpoint：

```bash
python -m app.main history --thread-id user-001
```

输出中的 `checkpoint_id` 是一次历史快照的精确标识，`next` 表示从该快照恢复时
准备执行的节点。先选择一个包含待修改数据的 Checkpoint，再创建分支。

审查最新 Checkpoint 中的资料和来源：

```bash
python -m app.main inspect --thread-id user-001
```

审查指定的历史 Checkpoint：

```bash
python -m app.main inspect \
  --thread-id user-001 \
  --checkpoint-id 1f0...
```

默认把审查内容打印到控制台。资料较多时，可以写入 Markdown 文件：

```bash
python -m app.main inspect \
  --thread-id user-001 \
  --checkpoint-id 1f0... \
  --output outputs/user-001-checkpoint-review.md
```

`inspect` 是只读命令，不执行 Graph 节点，也不调用 LLM。审查文档包含 Checkpoint
位置、研究计划、Evaluator 评分和意见、每个 Worker 的原始资料及其来源、Reducer
汇总来源、自动风险提示、人工核验清单和可复制的 `fork` 命令。自动提示只检查来源
为空、Worker 无来源、Evaluator 低于 80 分等 State 内部结构问题；URL 是否可访问、
来源是否权威、资料是否过期以及原文能否支持研究结论，仍需要人工核验。

## 时间旅行与人工修正

`fork` 会把指定 Checkpoint 的 State 复制到一个全新的线程。新线程拥有新的
`run_id`，因此 Checkpoint 历史和最终报告文件都与原任务隔离。程序使用
`graph.update_state(..., as_node=...)` 把修正后的 State 写入分支，并告诉 LangGraph
应把这次人工更新视为哪个节点的输出；随后用 `graph.stream(None, ...)` 从该节点的
后继节点继续执行。

修改 Planner 产生的计划：

```bash
python -m app.main fork \
  --thread-id user-001 \
  --checkpoint-id 1f0... \
  --new-thread-id user-001-plan-v2 \
  --plan "研究官方政策；核验行业数据；分析典型案例"
```

这类分支把人工修改视为 `plan_approval` 的结果，下一节点是
`prepare_research`。Planner 不会再次调用，旧计划产生的研究资料和下游草稿会被
清空，然后按新计划研究。

删除错误来源、删除错误文字并补充人工证据：

```bash
python -m app.main fork \
  --thread-id user-001 \
  --checkpoint-id 1f0... \
  --new-thread-id user-001-evidence-v2 \
  --remove-source "https://wrong.example/article" \
  --remove-text "这段结论已经被证伪" \
  --evidence "人工核验：官方统计为 42%。来源 https://official.example/data"
```

`--remove-source`、`--remove-text` 和 `--evidence` 都可以重复传入。人工证据中的
HTTP/HTTPS 链接会自动加入来源列表。这类分支把修正后的 State 视为
`research_reducer` 的输出，因此直接从 `research_evaluator` 开始；Planner 和已经
完成的 Research Worker 不会重跑。若 Evaluator 判断修正后的资料仍不足，正常的
研究循环仍可能开启一轮新的补充搜索。

也可以不提供修正参数，只把一个尚未结束的历史 Checkpoint 复制到新线程后按其
`next` 节点重放：

```bash
python -m app.main fork \
  --thread-id user-001 \
  --checkpoint-id 1f0...
```

程序会自动生成分支 `thread_id` 并打印出来。已经结束的 Checkpoint 没有后继节点，
因此必须提供计划或资料修正才能创建可执行分支。

分支会继承真正复用的历史用量，并把这些 `UsageEvent` 标记为 `inherited`；预算统计
仍包含这部分已经发生的 Token 和费用。修改计划时只保留 Planner 用量，修正资料时
保留 Planner 和 Researcher 用量，准备重跑的 Evaluator、Writer、Reviewer 的旧
用量会被删除，避免重复累计。

每个新任务应该使用新的 `thread_id`。如果 `run` 发现 ID 已存在，会拒绝覆盖，
避免旧状态和新状态意外合并。

控制台会显示各节点的执行状态和每次 LLM 调用的输出：Planner 的计划、
每个并行 Researcher 的研究摘要与来源、Writer 的 token 流，以及 Reviewer 的
评分与意见。
每个节点成功写入 State 后还会输出一条 `节点完成` 日志。
执行完成后，最终汇总结果还会写入：

```text
outputs/research-report-{run_id}.md
```

文件内容包括报告正文、人工确认后的研究计划、研究评估、审核信息、来源、估算
Token/费用和预算结束原因。`outputs/` 属于运行产物目录，已被 Git 忽略。

运行测试：

```bash
python -m unittest discover -v
```

测试使用 `FakeResearchLLM`，不会访问网络，也不会消耗 API 额度。测试覆盖瞬时
错误重试、永久错误分类、节点超时、调用预算、搜索轮数、用量费用与幂等文件写入。

### 手动验证 DeepSeek Researcher

以下命令会真实调用 DeepSeek 的 `Responses API` 和服务端网页搜索，可能消耗
API 额度；默认的测试套件会跳过它。请先在 `.env` 中配置
`LLM_PROVIDER=deepseek` 与 `DEEPSEEK_API_KEY`，然后执行：

```bash
RUN_DEEPSEEK_RESEARCH_MANUAL_TEST=1 \
python -m unittest -v tests.test_deepseek_research_manual
```

测试会把研究正文和来源 URL 输出到终端。可选地通过
`DEEPSEEK_RESEARCH_TOPIC` 自定义主题，或用以 `|` 分隔的
`DEEPSEEK_RESEARCH_TASKS` 自定义任务列表。

## 建议阅读顺序

1. `app/state.py`：先理解 Worker State、Result 和 `Annotated` Reducer。
2. `app/graph.py`：看 `dispatch_research_workers()` 如何动态创建 `Send`。
3. `app/nodes.py`：依次阅读 prepare、worker 和 reducer 三个节点。
4. `tests/test_graph.py`：看动态分发和真实并发如何验证。
5. `tests/test_checkpoints.py`：看并行分支失败后为什么只重试失败分支。
6. `app/streaming.py`：看多个 Worker 的自定义进度事件如何消费。
7. `app/runtime.py`：看 `max_concurrency` 如何限制并发。

注意：节点返回的是局部更新，而不是完整 State。LangGraph 会把这些更新
合并到当前 State 中，并把合并后的 State 交给下一个节点。
