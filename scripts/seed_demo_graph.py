from hea.shared.db import init_db
from hea.shared.registry import upsert_graph

DEMO_GRAPH = {
    "graph_id": "diabetes_demo_v1",
    "title": "Type 2 Diabetes Risk Assessment",
    "topic": "diabetes",
    "description": "Short assessment for type 2 diabetes risk.",
    "tags": ["diabetes", "glucose", "metabolic", "risk"],
    "entry_signals": ["диабет", "сухость во рту", "жажда", "glucose", "diabetes"],
    "questions": [
        {
            "id": "q1",
            "text": "Возраст",
            "question_type": "single_choice",
            "options": [
                {"label": "<45", "value": "lt45", "score": 0},
                {"label": "45-54", "value": "45_54", "score": 2},
                {"label": "55-64", "value": "55_64", "score": 3},
                {"label": ">64", "value": "gt64", "score": 4},
            ],
        },
        {
            "id": "q2",
            "text": "Индекс массы тела (ИМТ)",
            "question_type": "single_choice",
            "options": [
                {"label": "<25", "value": "lt25", "score": 0},
                {"label": "25-30", "value": "25_30", "score": 1},
                {"label": ">30", "value": "gt30", "score": 3},
            ],
        },
        {
            "id": "q3",
            "text": "Есть ли у вас родственники первой линии с диабетом?",
            "question_type": "single_choice",
            "options": [
                {"label": "Нет", "value": "no", "score": 0},
                {"label": "Да", "value": "yes", "score": 5},
            ],
        },
    ],
    "risk_bands": [
        {"min_score": 0, "max_score": 6, "label": "Low risk", "meaning": "Low estimated risk in this screening graph."},
        {"min_score": 7, "max_score": 11, "label": "Elevated risk", "meaning": "Elevated estimated risk in this screening graph."},
        {"min_score": 12, "max_score": 1000, "label": "High risk", "meaning": "High estimated risk in this screening graph."},
    ],
    "scoring": {"method": "sum_of_option_scores"},
}

if __name__ == "__main__":
    init_db()
    upsert_graph(DEMO_GRAPH)
    print("Seeded demo graph:", DEMO_GRAPH["graph_id"])
