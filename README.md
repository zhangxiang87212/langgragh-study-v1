# Mini Research Agent：第一阶段

这是一个刻意保持简单的 LangGraph 学习项目。当前阶段不调用真实大模型，
只用于理解 `State`、`Node`、`Edge`、`compile()` 和 `invoke()`。

工作流固定为：

```text
START → planner → researcher → writer → reviewer → END
```

## 运行项目

建议使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

使用默认主题运行：

```bash
python -m app.main
```

也可以在命令后传入自己的主题：

```bash
python -m app.main "研究 AI Agent 在教育领域的应用趋势"
```

运行测试：

```bash
python -m unittest discover -v
```

## 建议阅读顺序

1. `app/state.py`：先看所有节点共享的数据结构。
2. `app/nodes.py`：观察每个节点读取什么、只返回哪些更新。
3. `app/graph.py`：看节点如何通过边连接，以及如何编译。
4. `app/main.py`：看外部输入如何交给 Graph。
5. `tests/`：从断言反向确认每一部分的职责。

注意：节点返回的是局部更新，而不是完整 State。LangGraph 会把这些更新
合并到当前 State 中，并把合并后的 State 交给下一个节点。
