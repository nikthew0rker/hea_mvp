from fastapi import FastAPI

from shared.schemas import EvalRequest, EvalResponse

app = FastAPI(title="Evaluation Agent", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    """
    Healthcheck endpoint for the Evaluation Agent.
    """
    return {"status": "ok", "service": "evaluation-agent"}


@app.post("/run", response_model=EvalResponse)
async def run_eval(payload: EvalRequest) -> EvalResponse:
    """
    Run lightweight deterministic checks over a target payload.

    This scaffold keeps checks simple and explicit so the MVP
    has at least one QA and safety layer from day one.
    """
    checks = []

    if payload.target_type == "graph":
        graph = payload.payload
        checks.append(
            {
                "check_name": "graph_has_nodes",
                "status": "passed" if bool(graph.get("nodes")) else "failed",
                "message": "Graph contains nodes" if graph.get("nodes") else "Graph is missing nodes",
            }
        )
        checks.append(
            {
                "check_name": "graph_has_edges",
                "status": "passed" if bool(graph.get("edges")) else "failed",
                "message": "Graph contains edges" if graph.get("edges") else "Graph is missing edges",
            }
        )
    else:
        checks.append(
            {
                "check_name": "target_type_known",
                "status": "warning",
                "message": f"No specific checks implemented yet for target_type={payload.target_type}",
            }
        )

    overall = "failed" if any(c["status"] == "failed" for c in checks) else (
        "warning" if any(c["status"] == "warning" for c in checks) else "passed"
    )

    return EvalResponse(status=overall, checks=checks)
