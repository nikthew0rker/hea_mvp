from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from hea.graphs.patient_runtime.nodes import (
    answer_node,
    explain_result_node,
    help_node,
    repeat_question_node,
    route_runtime_message,
)
from hea.graphs.patient_runtime.state import PatientRuntimeState


def build_patient_runtime_graph():
    builder = StateGraph(PatientRuntimeState)

    builder.add_node("route_runtime_message", route_runtime_message)
    builder.add_node("repeat_question_node", repeat_question_node)
    builder.add_node("help_node", help_node)
    builder.add_node("explain_result_node", explain_result_node)
    builder.add_node("answer_node", answer_node)

    builder.add_edge(START, "route_runtime_message")
    builder.add_conditional_edges(
        "route_runtime_message",
        lambda state: state["next_action"],
        {
            "REPEAT": "repeat_question_node",
            "HELP": "help_node",
            "EXPLAIN_RESULT": "explain_result_node",
            "ANSWER": "answer_node",
        },
    )

    for node in [
        "repeat_question_node",
        "help_node",
        "explain_result_node",
        "answer_node",
    ]:
        builder.add_edge(node, END)

    return builder
