# waypoint/agent.py
# LangGraph agent graph — orchestrates the full Waypoint pipeline
# Nodes: ingest → rule_engine → llm_evaluation → save_flags
# This is the single entry point the Streamlit UI calls

from typing import TypedDict
from langgraph.graph import StateGraph, END

from waypoint.ingest import ingest_csv
from waypoint.db import get_all_students, insert_flag, get_all_flags
from waypoint.rules import run_rule_engine
from waypoint.llm import evaluate_batch
from config import CSV_PATH


# ── Agent State ───────────────────────────────────────────────────────────────
# TypedDict defines the state object that flows through every node
class WaypointState(TypedDict):
    csv_path: str
    ingest_summary: dict
    students: list
    clear_flags: list
    ambiguous: list
    no_flag: list
    llm_flags: list
    all_flags: list
    errors: list
    status: str


# ── Node: Ingest ──────────────────────────────────────────────────────────────
def node_ingest(state: WaypointState) -> WaypointState:
    """Load and normalize the CSV into SQLite."""
    print("[1/4] Ingesting CSV...")
    try:
        summary = ingest_csv(state["csv_path"])
        students = get_all_students()
        return {
            **state,
            "ingest_summary": summary,
            "students": students,
            "status": "ingested",
        }
    except Exception as e:
        return {
            **state,
            "errors": state["errors"] + [f"Ingest failed: {str(e)}"],
            "status": "error",
        }


# ── Node: Rule Engine ─────────────────────────────────────────────────────────
def node_rule_engine(state: WaypointState) -> WaypointState:
    """Run deterministic rules against all student records."""
    print("[2/4] Running rule engine...")
    try:
        results = run_rule_engine(state["students"])
        return {
            **state,
            "clear_flags": results["clear_flags"],
            "ambiguous": results["ambiguous"],
            "no_flag": results["no_flag"],
            "status": "rules_complete",
        }
    except Exception as e:
        return {
            **state,
            "errors": state["errors"] + [f"Rule engine failed: {str(e)}"],
            "status": "error",
        }


# ── Node: LLM Evaluation ─────────────────────────────────────────────────────
def node_llm_evaluation(state: WaypointState) -> WaypointState:
    """Send ambiguous cases to Claude for reasoning."""
    print(f"[3/4] Sending {len(state['ambiguous'])} ambiguous cases to Claude...")
    try:
        llm_flags = evaluate_batch(state["ambiguous"])
        return {
            **state,
            "llm_flags": llm_flags,
            "status": "llm_complete",
        }
    except Exception as e:
        return {
            **state,
            "errors": state["errors"] + [f"LLM evaluation failed: {str(e)}"],
            "llm_flags": [],
            "status": "llm_error",  # Non-fatal — deterministic flags still save
        }


# ── Node: Save Flags ──────────────────────────────────────────────────────────
def node_save_flags(state: WaypointState) -> WaypointState:
    """Persist all flags to the database."""
    print("[4/4] Saving flags to database...")
    try:
        # Save deterministic flags
        for flag in state["clear_flags"]:
            insert_flag({
                "student_id": flag["student_id"],
                "flag_type": flag["flag_type"],
                "flag_source": flag["flag_source"],
                "reasoning": flag["reasoning"],
                "outreach_note": flag["outreach_note"],
                "confidence": flag["confidence"],
            })

        # Save LLM flags
        for flag in state["llm_flags"]:
            insert_flag(flag)

        all_flags = get_all_flags()
        return {
            **state,
            "all_flags": all_flags,
            "status": "complete",
        }
    except Exception as e:
        return {
            **state,
            "errors": state["errors"] + [f"Save flags failed: {str(e)}"],
            "status": "error",
        }


# ── Routing ───────────────────────────────────────────────────────────────────
def should_continue(state: WaypointState) -> str:
    """Route to END if there's a fatal error, otherwise continue."""
    if state["status"] == "error":
        return "end"
    return "continue"


# ── Build Graph ───────────────────────────────────────────────────────────────
def build_graph():
    graph = StateGraph(WaypointState)

    graph.add_node("ingest", node_ingest)
    graph.add_node("rule_engine", node_rule_engine)
    graph.add_node("llm_evaluation", node_llm_evaluation)
    graph.add_node("save_flags", node_save_flags)

    graph.set_entry_point("ingest")

    graph.add_conditional_edges(
        "ingest",
        should_continue,
        {"continue": "rule_engine", "end": END}
    )
    graph.add_conditional_edges(
        "rule_engine",
        should_continue,
        {"continue": "llm_evaluation", "end": END}
    )
    # LLM errors are non-fatal — always proceed to save
    graph.add_edge("llm_evaluation", "save_flags")
    graph.add_edge("save_flags", END)

    return graph.compile()


# ── Public Entry Point ────────────────────────────────────────────────────────
def run_waypoint(csv_path: str = CSV_PATH) -> dict:
    """
    Run the full Waypoint pipeline.
    Returns the final state dict for the Streamlit UI to consume.
    """
    graph = build_graph()

    initial_state = WaypointState(
        csv_path=csv_path,
        ingest_summary={},
        students=[],
        clear_flags=[],
        ambiguous=[],
        no_flag=[],
        llm_flags=[],
        all_flags=[],
        errors=[],
        status="starting",
    )

    final_state = graph.invoke(initial_state)
    return final_state