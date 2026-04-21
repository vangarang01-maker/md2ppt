from langgraph.graph import StateGraph, END

from graph.state import PPTState
from graph.nodes.file_parser import node_file_parser
from graph.nodes.direction_agent import node_direction_agent
from graph.nodes.design_selector import node_design_selector
from graph.nodes.outline_planner import node_outline_planner
from graph.nodes.layout_validator import node_layout_validator
from pipeline.marp_renderer import render_marp


async def node_final_output(state: PPTState) -> dict:
    marp_md = state["marp_md"]
    slides_data = state.get("slides_data", {})
    design_system = state.get("design_system", {})

    brand = design_system.get("brand", "default")
    title = slides_data.get("title", "slides")
    output_dir = state.get("output_dir", "./output")

    out_path = await render_marp(marp_md, brand, output_dir, title)
    return {"output_path": out_path}


def _should_retry(state: PPTState) -> str:
    issues = state.get("validation_issues", [])
    count = state.get("iteration_count", 0)
    if issues and count < 3:
        return "outline_planner"
    return "final_output"


def build_graph():
    g = StateGraph(PPTState)

    g.add_node("file_parser",      node_file_parser)
    g.add_node("direction_agent",  node_direction_agent)
    g.add_node("design_selector",  node_design_selector)
    g.add_node("outline_planner",  node_outline_planner)
    g.add_node("layout_validator", node_layout_validator)
    g.add_node("final_output",     node_final_output)

    g.set_entry_point("file_parser")
    g.add_edge("file_parser",      "direction_agent")
    g.add_edge("direction_agent",  "design_selector")
    g.add_edge("design_selector",  "outline_planner")
    g.add_edge("outline_planner",  "layout_validator")
    g.add_conditional_edges("layout_validator", _should_retry)
    g.add_edge("final_output",     END)

    return g.compile()
