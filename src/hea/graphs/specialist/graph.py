from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from hea.graphs.specialist.nodes import (
    ack_language,
    apply_pending_proposal,
    compile_draft,
    discuss_specialist_goal,
    explain_question_source,
    publish_draft,
    reset_and_help,
    route_specialist_message,
    rollback_draft,
    show_diff,
    show_detailed_draft,
    show_help,
    show_preview,
    show_questions,
    show_risks,
    show_scoring,
    show_versions,
    update_draft,
)
from hea.graphs.specialist.state import SpecialistState


def build_specialist_graph():
    builder = StateGraph(SpecialistState)

    builder.add_node("route_specialist_message", route_specialist_message)
    builder.add_node("reset_and_help", reset_and_help)
    builder.add_node("ack_language", ack_language)
    builder.add_node("show_help", show_help)
    builder.add_node("discuss_specialist_goal", discuss_specialist_goal)
    builder.add_node("update_draft", update_draft)
    builder.add_node("show_diff", show_diff)
    builder.add_node("show_versions", show_versions)
    builder.add_node("rollback_draft", rollback_draft)
    builder.add_node("show_preview", show_preview)
    builder.add_node("show_detailed_draft", show_detailed_draft)
    builder.add_node("show_questions", show_questions)
    builder.add_node("show_scoring", show_scoring)
    builder.add_node("show_risks", show_risks)
    builder.add_node("explain_question_source", explain_question_source)
    builder.add_node("apply_pending_proposal", apply_pending_proposal)
    builder.add_node("compile_draft", compile_draft)
    builder.add_node("publish_draft", publish_draft)

    builder.add_edge(START, "route_specialist_message")
    builder.add_conditional_edges(
        "route_specialist_message",
        lambda state: state["next_action"],
        {
            "RESET_AND_HELP": "reset_and_help",
            "ACK_LANGUAGE": "ack_language",
            "SHOW_HELP": "show_help",
            "DISCUSS": "discuss_specialist_goal",
            "UPDATE_DRAFT": "update_draft",
            "SHOW_DIFF": "show_diff",
            "SHOW_VERSIONS": "show_versions",
            "ROLLBACK_DRAFT": "rollback_draft",
            "SHOW_PREVIEW": "show_preview",
            "SHOW_DETAILED_DRAFT": "show_detailed_draft",
            "SHOW_QUESTIONS": "show_questions",
            "SHOW_SCORING": "show_scoring",
            "SHOW_RISKS": "show_risks",
            "EXPLAIN_QUESTION_SOURCE": "explain_question_source",
            "APPLY_PENDING_PROPOSAL": "apply_pending_proposal",
            "COMPILE": "compile_draft",
            "PUBLISH": "publish_draft",
        },
    )

    for node in [
        "reset_and_help",
        "ack_language",
        "show_help",
        "discuss_specialist_goal",
        "update_draft",
        "show_diff",
        "show_versions",
        "rollback_draft",
        "show_preview",
        "show_detailed_draft",
        "show_questions",
        "show_scoring",
        "show_risks",
        "explain_question_source",
        "apply_pending_proposal",
        "compile_draft",
        "publish_draft",
    ]:
        builder.add_edge(node, END)

    return builder
