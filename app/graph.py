"""Build and compile the research graph."""

from langgraph.graph import END, START, StateGraph

from app.nodes import planner_node, researcher_node, reviewer_node, writer_node
from app.state import ResearchState


def build_graph():
    """Create the graph structure and return its compiled form."""

    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("writer", writer_node)
    builder.add_node("reviewer", reviewer_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "writer")
    builder.add_edge("writer", "reviewer")
    builder.add_edge("reviewer", END)

    return builder.compile()


graph = build_graph()
