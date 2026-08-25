# Mini Research Agent：第七阶段

当前阶段增加了 Human-in-the-loop。Planner 生成研究计划后，Graph 会暂停，
等待用户确认或修改计划，然后才允许 Researcher 执行收费的网页搜索。

- Planner：使用结构化输出生成 3 到 6 个研究任务。
- Plan Approval：暂停 Graph，让用户确认或替换研究计划。
- Researcher：调用 Responses API 的 `web_search` 工具，汇总资料和来源 URL。
- Research Evaluator：评估任务覆盖度、来源质量、时效性和证据充分度。
- Writer：根据资料生成 Markdown 报告，并在循环中接收审核意见。
- Reviewer：使用结构化输出返回 0 到 100 分和修改意见。

当前工作流为：

```text
START → planner → plan_approval → researcher → research_evaluator
                         ↑             ↑                    │
                  Command(resume)    资料不足             │ 资料足够
                         ↑             └──────────────────┘
                    用户确认/修改                           ↓
                                                    writer → reviewer
                                                       ↑          ├─ score >= 80 → END
                                                       └──────────┤ score < 80
                                                                  └─ 重写 >= 3 → END
```

## 暂停和恢复

`plan_approval_node()` 通过 `interrupt()` 把研究计划交给调用方：

```python
decision = interrupt(
    {
        "question": "请确认研究计划后再继续。",
        "plan": state["plan"],
    }
)
```

第一次 `invoke()` 不会执行 Researcher，而是在 `__interrupt__` 中返回
等待处理的内容。用户做出决定后，程序使用相同的 `thread_id` 恢复：

```python
result = graph.invoke(
    Command(resume={"action": "approve"}),
    config=config,
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

Graph 在编译时使用 `InMemorySaver`：

```python
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
```

每次调用 Graph 时都需要传入线程配置：

```python
config = {"configurable": {"thread_id": "user-001"}}
result = graph.invoke(initial_state, config=config)
```

`thread_id` 不是 State 字段。它是 Checkpointer 用来区分不同执行线程的键。
两个不同的 `thread_id` 会保存两组独立的 State 和历史快照。

```python
snapshot = graph.get_state(config)
history = list(graph.get_state_history(config))
```

`snapshot.values` 是当前快照中的 State，`snapshot.next` 是接下来要执行的节点。
工作流正常结束后，`snapshot.next` 是空元组。

`InMemorySaver` 只适合学习和测试。数据只存在当前 Python 进程内；命令结束后，
下一次启动无法恢复上次的快照。后续工业化时应替换为 SQLite 或 PostgreSQL
Checkpointer。

Researcher 会把两类数据写入 State：

- `research_content`：模型根据搜索结果整理的中文研究资料。
- `sources`：从 Web Search 工具调用中提取并去重的来源 URL。

搜索被设置为 `required`，避免模型跳过工具直接凭记忆回答。OpenAI
模式下，每轮 Researcher 最多允许 6 次 Web Search 工具调用；Graph
最多研究 3 轮，因此理论上限是 18 次。DeepSeek 模式下，官方文档明确
说明 `max_tool_calls` 会被忽略，每次 Responses API 请求的服务端自动续行
最多 10 轮；项目仍通过 Graph 的 3 轮研究上限控制总流程。

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

使用默认主题运行：

```bash
python -m app.main
```

也可以在命令后传入自己的主题：

```bash
python -m app.main "研究 AI Agent 在教育领域的应用趋势"
```

指定一个 Checkpoint 线程：

```bash
python -m app.main "研究 AI Agent 在教育领域的应用趋势" --thread-id user-001
```

如果不传 `--thread-id`，程序会生成一个 UUID，并把它记录到控制台。
当 Planner 输出计划后：

- 直接按 Enter：批准原计划。
- 输入新任务：替换原计划，多个任务使用中文或英文分号分隔。

控制台会显示各节点的执行状态和每次 LLM 调用的输出：Planner 的计划、
Researcher 的研究摘要与来源、Writer 的完整草稿，以及 Reviewer 的评分与意见。
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

1. `app/nodes.py`：阅读 `plan_approval_node()` 中的 `interrupt()`。
2. `app/graph.py`：看确认节点为什么位于 Planner 和 Researcher 之间。
3. `app/human.py`：看控制台输入如何转换成可序列化的决定。
4. `app/main.py`：跟踪首次 `invoke()`、`__interrupt__` 和 `Command(resume=...)`。
5. `app/config.py` 和 `app/llm.py`：看 Provider 工厂和两种 Responses Web Search 实现。
6. `tests/test_graph.py`：看两个质量循环的分支和上限如何测试。
7. `app/runtime.py`：回顾 Checkpoint 为什么需要 `thread_id`。

注意：节点返回的是局部更新，而不是完整 State。LangGraph 会把这些更新
合并到当前 State 中，并把合并后的 State 交给下一个节点。
