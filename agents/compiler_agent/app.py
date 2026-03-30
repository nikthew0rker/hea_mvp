from fastapi import FastAPI

from shared.schemas import CompileRequest, CompileResponse

app = FastAPI(title="Compiler Agent", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    """
    Healthcheck endpoint for the Compiler Agent.
    """
    return {"status": "ok", "service": "compiler-agent"}


@app.post("/compile", response_model=CompileResponse)
async def compile_draft(payload: CompileRequest) -> CompileResponse:
    """
    Convert a structured draft into a compiled graph artifact.

    This scaffold returns a minimal graph shape.
    In the real implementation this should become the canonical executable graph.
    """
    graph = {
        "graph_version_id": "graph_v1_demo",
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "q1", "type": "question", "goal": "collect user sleep quality"},
            {"id": "finish", "type": "finish"},
        ],
        "edges": [
            {"from": "start", "to": "q1", "condition": "always"},
            {"from": "q1", "to": "finish", "condition": "always"},
        ],
        "guardrails": {
            "no_diagnosis": True,
            "no_treatment_plan": True,
            "no_medication_recommendation": True,
        },
    }

    return CompileResponse(
        status="compiled",
        graph_version_id="graph_v1_demo",
        graph=graph,
        feedback=[],
    )
