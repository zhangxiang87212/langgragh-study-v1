"""Consume LangGraph stream events and render concise console logs."""

from typing import Any


STREAM_MODES = ["updates", "custom"]


def run_graph_stream(graph, graph_input, config) -> dict[str, Any]:
    """Run a graph stream and return the final persisted state."""

    interrupt_update = None
    for part in graph.stream(
        graph_input,
        config=config,
        stream_mode=STREAM_MODES,
        version="v2",
    ):
        if part["type"] == "custom":
            render_custom_event(part["data"])
            continue

        if part["type"] == "updates":
            interrupt_update = render_state_updates(
                part["data"],
                interrupt_update,
            )

    snapshot = graph.get_state(config)
    result = dict(snapshot.values)
    if interrupt_update is not None:
        result["__interrupt__"] = interrupt_update

    return result


def render_state_updates(updates: dict[str, Any], current_interrupt):
    """Log completed nodes and remember an interrupt update."""

    interrupt_update = current_interrupt
    for node_name, update in updates.items():
        if node_name == "__interrupt__":
            interrupt_update = update
        else:
            print(f"节点完成：{node_name}")

    return interrupt_update


def render_custom_event(event: dict[str, Any]) -> None:
    """Print token events emitted by an arbitrary LLM client."""

    event_type = event.get("event")
    if event_type == "llm_stream_start":
        print(f"{event['node']} 流式输出：")
    elif event_type == "llm_token":
        print(event["text"], end="", flush=True)
    elif event_type == "llm_stream_end":
        print()
