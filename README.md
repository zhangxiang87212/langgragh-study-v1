# Mini Research Agent：第十阶段

当前阶段把单个 Researcher 升级为动态 Map-Reduce。Planner 的每个任务通过
`Send` 创建一个独立 `research_worker`，这些 Worker 在同一个 superstep 中并行
搜索；带 Reducer 的 `research_results` 收集所有结果，再由 `research_reducer`
按计划顺序合并。流式日志、人工审批和 SQLite 跨进程恢复继续保留。

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

然后编辑 `.env`。使用 OpenAI 作为主模型：

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

`.env` 已被 Git 忽略，不要把任何真实 API Key 写入 `.env.example`
或提交到代码仓库。

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

每个新任务应该使用新的 `thread_id`。如果 `run` 发现 ID 已存在，会拒绝覆盖，
避免旧状态和新状态意外合并。

控制台会显示各节点的执行状态和每次 LLM 调用的输出：Planner 的计划、
每个并行 Researcher 的研究摘要与来源、Writer 的 token 流，以及 Reviewer 的
评分与意见。
每个节点成功写入 State 后还会输出一条 `节点完成` 日志。
执行完成后，最终汇总结果还会写入：

```text
outputs/research-report-时间戳.md
```

文件内容包括报告正文、人工确认后的研究计划、研究评估、审核信息和来源。`outputs/`
属于运行产物目录，已被 Git 忽略。

运行测试：

```bash
python -m unittest discover -v
```

测试使用 `FakeResearchLLM`，不会访问网络，也不会消耗 API 额度。一次正常运行
至少调用模型 4 次，并发生至少一次收费的 Web Search 工具调用；每轮重写会再
调用 Writer 和 Reviewer 各一次。

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
