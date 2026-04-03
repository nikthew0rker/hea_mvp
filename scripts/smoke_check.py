from hea.shared.db import init_db
from hea.shared.registry import upsert_graph
from hea.shared.search import search_graphs
from hea.shared.runtime import create_assessment_state, render_question, normalize_answer, apply_answer

def main():
    init_db()
    graph = {
        "graph_id": "smoke_graph_v1",
        "title": "Smoke Graph",
        "topic": "smoke",
        "description": "Simple smoke test graph",
        "tags": ["smoke"],
        "entry_signals": ["smoke"],
        "questions": [
            {
                "id": "q1",
                "text": "Do you smoke?",
                "question_type": "single_choice",
                "options": [
                    {"label": "No", "value": "no", "score": 0},
                    {"label": "Yes", "value": "yes", "score": 3},
                ],
            }
        ],
        "risk_bands": [
            {"min_score": 0, "max_score": 0, "label": "Low", "meaning": "Low"},
            {"min_score": 1, "max_score": 1000, "label": "Elevated", "meaning": "Elevated"},
        ],
        "scoring": {"method": "sum_of_option_scores"},
    }
    upsert_graph(graph)
    results = search_graphs("smoke")
    assert results, "search returned no results"
    state = create_assessment_state(graph, "en")
    assert "Question 1/1" in render_question(graph, state)
    normalized = normalize_answer(graph["questions"][0], "2")
    applied = apply_answer(graph, state, normalized)
    assert applied["completed"] is True
    print("smoke check passed")

if __name__ == "__main__":
    main()
