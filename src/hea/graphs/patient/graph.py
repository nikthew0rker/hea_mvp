from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from hea.graphs.patient.nodes import (
    cancel_assessment,
    decline_assessment,
    explain_current_result,
    explain_last_result_node,
    pause_assessment,
    red_flag_guidance,
    restate_consent,
    reset_and_greet,
    reset_to_free,
    resume_assessment,
    route_user_message,
    search_assessments,
    select_candidate,
    show_capabilities,
    show_current_report,
    show_current_result,
    show_last_report,
    show_last_result,
    show_post_options,
    show_paused,
    start_assessment,
)
from hea.graphs.patient.state import PatientState
from hea.graphs.patient_runtime.graph import build_patient_runtime_graph


def build_patient_graph():
    runtime_subgraph = build_patient_runtime_graph().compile()
    builder = StateGraph(PatientState)

    async def run_runtime_subgraph_node(state: PatientState):
        graph = state.get("selected_graph") or {}
        assessment_state = state.get("assessment_state") or {}
        result = await runtime_subgraph.ainvoke(
            {
                "graph": graph,
                "assessment_state": assessment_state,
                "user_message": state.get("user_message"),
            }
        )
        return {
            "assessment_state": result.get("assessment_state"),
            "assistant_reply": result.get("assistant_reply"),
        }

    builder.add_node("route_user_message", route_user_message)
    builder.add_node("reset_and_greet", reset_and_greet)
    builder.add_node("reset_to_free", reset_to_free)
    builder.add_node("show_capabilities", show_capabilities)
    builder.add_node("red_flag_guidance", red_flag_guidance)
    builder.add_node("restate_consent", restate_consent)
    builder.add_node("search_assessments", search_assessments)
    builder.add_node("select_candidate", select_candidate)
    builder.add_node("decline_assessment", decline_assessment)
    builder.add_node("start_assessment", start_assessment)
    builder.add_node("pause_assessment", pause_assessment)
    builder.add_node("resume_assessment", resume_assessment)
    builder.add_node("cancel_assessment", cancel_assessment)
    builder.add_node("show_paused", show_paused)
    builder.add_node("show_current_result", show_current_result)
    builder.add_node("show_current_report", show_current_report)
    builder.add_node("explain_current_result", explain_current_result)
    builder.add_node("show_last_result", show_last_result)
    builder.add_node("show_last_report", show_last_report)
    builder.add_node("explain_last_result_node", explain_last_result_node)
    builder.add_node("show_post_options", show_post_options)
    builder.add_node("run_runtime_subgraph", run_runtime_subgraph_node)

    builder.add_edge(START, "route_user_message")
    builder.add_conditional_edges(
        "route_user_message",
        lambda state: state["next_action"],
        {
            "RESET_AND_GREET": "reset_and_greet",
            "RESET_TO_FREE": "reset_to_free",
            "SHOW_CAPABILITIES": "show_capabilities",
            "RED_FLAG_GUIDANCE": "red_flag_guidance",
            "SEARCH": "search_assessments",
            "SELECT_CANDIDATE": "select_candidate",
            "RESTATE_CONSENT": "restate_consent",
            "DECLINE": "decline_assessment",
            "START_ASSESSMENT": "start_assessment",
            "PAUSE": "pause_assessment",
            "RESUME": "resume_assessment",
            "CANCEL": "cancel_assessment",
            "SHOW_PAUSED": "show_paused",
            "SHOW_CURRENT_RESULT": "show_current_result",
            "SHOW_CURRENT_REPORT": "show_current_report",
            "EXPLAIN_CURRENT_RESULT": "explain_current_result",
            "SHOW_LAST_RESULT": "show_last_result",
            "SHOW_LAST_REPORT": "show_last_report",
            "EXPLAIN_LAST_RESULT": "explain_last_result_node",
            "SHOW_POST_OPTIONS": "show_post_options",
            "RUN_RUNTIME_SUBGRAPH": "run_runtime_subgraph",
        },
    )

    terminal_nodes = [
        "reset_and_greet",
        "reset_to_free",
        "show_capabilities",
        "red_flag_guidance",
        "restate_consent",
        "search_assessments",
        "select_candidate",
        "decline_assessment",
        "start_assessment",
        "pause_assessment",
        "resume_assessment",
        "cancel_assessment",
        "show_paused",
        "show_current_result",
        "show_current_report",
        "explain_current_result",
        "show_last_result",
        "show_last_report",
        "explain_last_result_node",
        "show_post_options",
        "run_runtime_subgraph",
    ]
    for node in terminal_nodes:
        builder.add_edge(node, END)

    return builder
