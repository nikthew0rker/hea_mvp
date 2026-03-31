#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-.}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${ROOT_DIR}/.backup_patient_orchestration_${STAMP}"

log()  { printf "[INFO] %s\n" "$*"; }
ok()   { printf "[ OK ] %s\n" "$*"; }
warn() { printf "[WARN] %s\n" "$*"; }
fail() { printf "[FAIL] %s\n" "$*" >&2; exit 1; }

need_dir() {
  [ -d "$1" ] || fail "Directory not found: $1"
}

backup_if_exists() {
  local rel="$1"
  local src="${ROOT_DIR}/${rel}"
  local dst="${BACKUP_DIR}/${rel}"
  if [ -e "${src}" ]; then
    mkdir -p "$(dirname "${dst}")"
    if [ -d "${src}" ]; then
      cp -R "${src}" "${dst}"
    else
      cp "${src}" "${dst}"
    fi
    ok "Backed up: ${rel}"
  else
    warn "No existing path to back up: ${rel}"
  fi
}

write_file() {
  local rel="$1"
  local abs="${ROOT_DIR}/${rel}"
  mkdir -p "$(dirname "${abs}")"
  cat > "${abs}"
  [ -f "${abs}" ] || fail "Failed to write: ${rel}"
  ok "Installed: ${rel}"
}

check_file() {
  local rel="$1"
  [ -f "${ROOT_DIR}/${rel}" ] || fail "Missing expected file: ${rel}"
  ok "Verified file: ${rel}"
}

log "Target project root: ${ROOT_DIR}"
need_dir "${ROOT_DIR}"
mkdir -p "${BACKUP_DIR}"
ok "Created backup directory: ${BACKUP_DIR}"

for rel in \
  shared/config.py \
  shared/graph_registry.py \
  shared/published_graph_store.py \
  shared/patient_session_store.py \
  shared/patient_graph_runtime.py \
  agents/patient_controller/app.py \
  agents/compiler_agent/app.py \
  bots/user_bot/bot.py \
  .env.example \
  docker-compose.yml \
  run_patient_controller.sh
do
  backup_if_exists "$rel"
done

write_file "shared/config.py" <<'EOF'
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Shared project settings including patient orchestration layer.
    """

    together_api_key: str = Field(default="")
    together_model: str = Field(default="Qwen/Qwen3.5-9B")

    specialist_controller_model: str = Field(default="zai-org/GLM-5")
    patient_controller_model: str = Field(default="zai-org/GLM-5")
    definition_agent_model: str = Field(default="Qwen/Qwen3.5-397B-A17B")
    runtime_agent_model: str = Field(default="Qwen/Qwen3.5-9B")
    report_agent_model: str = Field(default="Qwen/Qwen3.5-9B")
    evaluation_agent_model: str = Field(default="Qwen/Qwen3.5-9B")

    specialist_bot_token: str = Field(default="")
    user_bot_token: str = Field(default="")

    definition_agent_url: str = Field(default="http://definition-agent:8000")
    compiler_agent_url: str = Field(default="http://compiler-agent:8000")
    runtime_agent_url: str = Field(default="http://runtime-agent:8000")
    report_agent_url: str = Field(default="http://report-agent:8000")
    evaluation_agent_url: str = Field(default="http://evaluation-agent:8000")
    patient_controller_url: str = Field(default="http://patient-controller:8000")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return one cached Settings instance.
    """
    return Settings()
EOF

write_file "shared/graph_registry.py" <<'EOF'
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.json_store import JSONStore


DATA_DIR = Path("data")
GRAPH_REGISTRY_STORE = JSONStore(DATA_DIR / "graph_registry.json", default=[])


def _ensure_store() -> None:
    """
    Ensure the graph registry store exists.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GRAPH_REGISTRY_STORE.ensure_exists()


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_]+", text.lower())
        if len(token) >= 3
    }


def _collect_question_texts(graph_payload: dict[str, Any]) -> list[str]:
    texts: list[str] = []

    questions = graph_payload.get("questions")
    if isinstance(questions, list):
        for q in questions:
            if isinstance(q, dict):
                text = q.get("text")
                if isinstance(text, str):
                    texts.append(text)

    source_draft = graph_payload.get("source_draft", {})
    if isinstance(source_draft, dict):
        draft_questions = source_draft.get("candidate_questions")
        if isinstance(draft_questions, list):
            for q in draft_questions:
                if isinstance(q, dict):
                    text = q.get("text")
                    if isinstance(text, str):
                        texts.append(text)

    return texts


def derive_graph_metadata(graph_id: str, graph_payload: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Derive searchable metadata for a graph.

    This keeps the registry graph-agnostic while still giving the patient
    orchestrator enough information to search the graph library.
    """
    metadata = metadata or {}

    title = (
        graph_payload.get("title")
        or graph_payload.get("topic")
        or (graph_payload.get("source_draft", {}) or {}).get("understood", {}).get("topic")
        or graph_id
    )

    topic = (
        graph_payload.get("topic")
        or (graph_payload.get("source_draft", {}) or {}).get("understood", {}).get("topic")
        or title
    )

    questions = graph_payload.get("questions")
    if isinstance(questions, list):
        questions_count = len(questions)
    else:
        source_draft = graph_payload.get("source_draft", {})
        if isinstance(source_draft, dict) and isinstance(source_draft.get("candidate_questions"), list):
            questions_count = len(source_draft.get("candidate_questions"))
        else:
            questions_count = 0

    estimated_time_minutes = max(1, (questions_count + 2) // 3) if questions_count else 2

    question_texts = _collect_question_texts(graph_payload)
    seed_text = " ".join([str(title), str(topic)] + question_texts[:8])

    tags = set()
    tags.update(_tokenize(str(topic)))
    tags.update(_tokenize(str(title)))

    provided_tags = metadata.get("tags")
    if isinstance(provided_tags, list):
        for tag in provided_tags:
            if isinstance(tag, str):
                tags.add(tag.lower())

    entry_signals = metadata.get("entry_signals")
    if not isinstance(entry_signals, list):
        entry_signals = sorted(list(tags))[:8]

    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        description = f"Assessment related to {topic}"

    return {
        "title": title,
        "topic": topic,
        "description": description,
        "tags": sorted(list(tags)),
        "entry_signals": entry_signals,
        "questions_count": questions_count,
        "estimated_time_minutes": estimated_time_minutes,
        "search_text": seed_text,
    }


def upsert_graph_in_registry(graph_id: str, graph_payload: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Insert or update a graph entry in the library registry.
    """
    _ensure_store()
    payload = GRAPH_REGISTRY_STORE.load()
    if not isinstance(payload, list):
        payload = []

    derived_metadata = derive_graph_metadata(graph_id, graph_payload, metadata)

    entry = {
        "graph_id": graph_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "published": True,
        "metadata": derived_metadata,
        "graph": graph_payload,
    }

    replaced = False
    for idx, item in enumerate(payload):
        if isinstance(item, dict) and item.get("graph_id") == graph_id:
            payload[idx] = entry
            replaced = True
            break

    if not replaced:
        payload.append(entry)

    GRAPH_REGISTRY_STORE.save(payload)
    return entry


def load_graph_library() -> list[dict[str, Any]]:
    """
    Load all graph entries from registry.
    """
    _ensure_store()
    payload = GRAPH_REGISTRY_STORE.load()
    return payload if isinstance(payload, list) else []


def get_graph_record(graph_id: str) -> dict[str, Any] | None:
    """
    Return one graph registry entry by id.
    """
    for item in load_graph_library():
        if isinstance(item, dict) and item.get("graph_id") == graph_id:
            return item
    return None


def search_graphs(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Search graph library using simple heuristic scoring.

    This intentionally stays graph-agnostic and does not assume a specific domain.
    """
    query_tokens = _tokenize(query)
    query_lower = query.lower()

    results: list[dict[str, Any]] = []
    for item in load_graph_library():
        if not isinstance(item, dict):
            continue

        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            continue

        title = str(metadata.get("title", ""))
        description = str(metadata.get("description", ""))
        topic = str(metadata.get("topic", ""))
        tags = metadata.get("tags", [])
        entry_signals = metadata.get("entry_signals", [])
        search_text = str(metadata.get("search_text", ""))

        score = 0.0
        reasons: list[str] = []

        meta_text = " ".join(
            [title, description, topic, search_text]
            + [str(t) for t in tags if isinstance(t, str)]
            + [str(s) for s in entry_signals if isinstance(s, str)]
        )
        meta_tokens = _tokenize(meta_text)

        overlap = query_tokens & meta_tokens
        if overlap:
            score += float(len(overlap)) * 2.0
            reasons.append(f"token overlap: {', '.join(sorted(list(overlap))[:4])}")

        for signal in entry_signals:
            if isinstance(signal, str) and signal.lower() in query_lower:
                score += 4.0
                reasons.append(f"matched signal: {signal}")

        for tag in tags:
            if isinstance(tag, str) and tag.lower() in query_lower:
                score += 3.0
                reasons.append(f"matched tag: {tag}")

        if title and title.lower() in query_lower:
            score += 4.0
            reasons.append("matched title")

        if topic and topic.lower() in query_lower:
            score += 3.0
            reasons.append("matched topic")

        if score > 0:
            results.append(
                {
                    "graph_id": item.get("graph_id"),
                    "score": score,
                    "reason": "; ".join(reasons[:3]),
                    "metadata": metadata,
                    "graph": item.get("graph"),
                }
            )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def list_graph_summaries(limit: int = 10) -> list[dict[str, Any]]:
    """
    Return lightweight graph summaries for capabilities listing.
    """
    summaries: list[dict[str, Any]] = []
    for item in load_graph_library()[:limit]:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        summaries.append(
            {
                "graph_id": item.get("graph_id"),
                "title": metadata.get("title") or item.get("graph_id"),
                "description": metadata.get("description"),
                "questions_count": metadata.get("questions_count"),
                "estimated_time_minutes": metadata.get("estimated_time_minutes"),
                "tags": metadata.get("tags", []),
            }
        )
    return summaries
EOF

write_file "shared/published_graph_store.py" <<'EOF'
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.graph_registry import upsert_graph_in_registry
from shared.json_store import JSONStore


DATA_DIR = Path("data")

ACTIVE_GRAPH_STORE = JSONStore(
    DATA_DIR / "active_graph.json",
    default={
        "graph_id": None,
        "status": None,
        "is_active": False,
        "published_at": None,
        "metadata": {},
        "graph": None,
    },
)


def _ensure_data_dir() -> None:
    """
    Ensure that the local data directory and backing JSON files exist.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_GRAPH_STORE.ensure_exists()


def publish_graph(graph_id: str, graph_payload: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Publish a graph by writing it into local shared storage and registry.

    Behavior:
    - active_graph.json keeps the most recently published graph
    - graph_registry.json accumulates all published graphs as a searchable library
    """
    _ensure_data_dir()

    record = {
        "graph_id": graph_id,
        "status": "published",
        "is_active": True,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
        "graph": graph_payload,
    }

    ACTIVE_GRAPH_STORE.save(record)
    registry_entry = upsert_graph_in_registry(graph_id, graph_payload, metadata or {})

    return {
        "graph_id": graph_id,
        "active_graph_file": str(ACTIVE_GRAPH_STORE.path),
        "registry_entry": registry_entry,
    }


def load_active_graph_record() -> dict[str, Any] | None:
    """
    Load the currently active graph record.
    """
    _ensure_data_dir()
    payload = ACTIVE_GRAPH_STORE.load()
    return payload if isinstance(payload, dict) else None


def load_active_graph() -> dict[str, Any] | None:
    """
    Load only the active graph payload.
    """
    record = load_active_graph_record()
    if not record:
        return None
    graph = record.get("graph")
    return graph if isinstance(graph, dict) else None


def get_active_graph_id() -> str | None:
    """
    Return the current active graph id, if any.
    """
    record = load_active_graph_record()
    if not record:
        return None
    graph_id = record.get("graph_id")
    return graph_id if isinstance(graph_id, str) else None
EOF

write_file "shared/patient_session_store.py" <<'EOF'
from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.json_store import JSONStore


DATA_DIR = Path("data")
SESSION_STORE = JSONStore(DATA_DIR / "patient_sessions.json", default={})


def _ensure_store() -> None:
    """
    Ensure the patient session store exists.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_STORE.ensure_exists()


def load_session(conversation_id: str) -> dict[str, Any] | None:
    """
    Load one patient session by conversation id.
    """
    _ensure_store()
    payload = SESSION_STORE.load()
    if not isinstance(payload, dict):
        return None
    session = payload.get(conversation_id)
    return session if isinstance(session, dict) else None


def save_session(conversation_id: str, session: dict[str, Any]) -> dict[str, Any]:
    """
    Save one patient session by conversation id.
    """
    _ensure_store()
    payload = SESSION_STORE.load()
    if not isinstance(payload, dict):
        payload = {}
    payload[conversation_id] = session
    SESSION_STORE.save(payload)
    return session


def delete_session(conversation_id: str) -> None:
    """
    Delete one patient session.
    """
    _ensure_store()
    payload = SESSION_STORE.load()
    if not isinstance(payload, dict):
        payload = {}
    payload.pop(conversation_id, None)
    SESSION_STORE.save(payload)
EOF

write_file "shared/patient_graph_runtime.py" <<'EOF'
from __future__ import annotations

import re
from typing import Any


YES_WORDS_RU = {"да", "ага", "угу", "есть", "было", "конечно", "хочу", "начнем", "начинаем"}
NO_WORDS_RU = {"нет", "не", "не было", "отсутствует", "не хочу"}
YES_WORDS_EN = {"yes", "y", "yeah", "yep", "true", "sure", "start"}
NO_WORDS_EN = {"no", "n", "nope", "false"}


def detect_language(text: str) -> str:
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "ru"
    return "en"


def localize_text(value: Any, language: str, fallback: str = "") -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        chosen = value.get(language)
        if isinstance(chosen, str) and chosen.strip():
            return chosen
        for candidate in value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    return fallback


def extract_runtime_graph(graph_record: dict[str, Any] | None) -> dict[str, Any]:
    """
    Convert a registry record or active graph record into a runtime-friendly graph.
    """
    if not isinstance(graph_record, dict):
        return {
            "graph_id": None,
            "title": "assessment",
            "topic": "assessment",
            "entry_node_id": None,
            "nodes": [],
            "risk_bands": [],
            "scoring": {},
        }

    graph_id = graph_record.get("graph_id")
    graph = graph_record.get("graph", {})
    if not isinstance(graph, dict):
        graph = {}

    if isinstance(graph.get("nodes"), list) and graph.get("nodes"):
        return {
            "graph_id": graph_id,
            "title": graph.get("title") or graph.get("topic") or graph_id or "assessment",
            "topic": graph.get("topic") or graph.get("title") or "assessment",
            "entry_node_id": graph.get("entry_node_id") or _first_node_id(graph.get("nodes")),
            "nodes": _normalize_nodes(graph.get("nodes")),
            "risk_bands": graph.get("risk_bands", []) if isinstance(graph.get("risk_bands"), list) else [],
            "scoring": graph.get("scoring", {}) if isinstance(graph.get("scoring"), dict) else {},
        }

    questions = graph.get("questions")
    if not isinstance(questions, list):
        source_draft = graph.get("source_draft", {})
        if isinstance(source_draft, dict):
            questions = source_draft.get("candidate_questions", [])
        else:
            questions = []

    source_draft = graph.get("source_draft", {})
    if not isinstance(source_draft, dict):
        source_draft = {}

    return build_sequential_runtime_graph(
        graph_id=graph_id,
        title=graph.get("title") or graph.get("topic") or graph_id or "assessment",
        topic=graph.get("topic") or graph.get("title") or "assessment",
        questions=questions if isinstance(questions, list) else [],
        risk_bands=graph.get("risk_bands", []) if isinstance(graph.get("risk_bands"), list) else (
            source_draft.get("candidate_risk_bands", []) if isinstance(source_draft.get("candidate_risk_bands"), list) else []
        ),
        scoring=graph.get("scoring", {}) if isinstance(graph.get("scoring"), dict) else (
            source_draft.get("candidate_scoring_rules", {}) if isinstance(source_draft.get("candidate_scoring_rules"), dict) else {}
        ),
    )


def build_sequential_runtime_graph(
    *,
    graph_id: str | None,
    title: str,
    topic: str,
    questions: list[dict[str, Any]],
    risk_bands: list[dict[str, Any]],
    scoring: dict[str, Any],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []

    for idx, raw_q in enumerate(questions):
        if not isinstance(raw_q, dict):
            continue

        node_id = str(raw_q.get("id") or f"q{idx + 1}")
        next_id = str(questions[idx + 1].get("id") or f"q{idx + 2}") if idx + 1 < len(questions) and isinstance(questions[idx + 1], dict) else "result"
        q_type, normalization_rule, validation_rule = infer_runtime_rules(raw_q)

        nodes.append(
            {
                "id": node_id,
                "type": "question",
                "question_type": raw_q.get("question_type", q_type),
                "text": raw_q.get("text", f"Question {idx + 1}"),
                "help_text": raw_q.get("help_text") or _default_help_for_question(raw_q, q_type),
                "why_it_matters": raw_q.get("why_it_matters"),
                "options": _normalize_options(raw_q.get("options")),
                "normalization_rule": raw_q.get("normalization_rule") or normalization_rule,
                "validation_rule": raw_q.get("validation_rule") or validation_rule,
                "scoring_rule": raw_q.get("scoring_rule") or {"type": "selected_option_score"},
                "next": {"default": next_id},
            }
        )

    nodes.append(
        {
            "id": "result",
            "type": "result",
            "text": {"ru": "Результат assessment", "en": "Assessment result"},
            "next": {},
        }
    )

    return {
        "graph_id": graph_id,
        "title": title,
        "topic": topic,
        "entry_node_id": nodes[0]["id"] if nodes else None,
        "nodes": nodes,
        "risk_bands": risk_bands if isinstance(risk_bands, list) else [],
        "scoring": scoring if isinstance(scoring, dict) else {},
    }


def infer_runtime_rules(question: dict[str, Any]) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    text = str(question.get("text", "")).lower()
    options = question.get("options", [])
    options = options if isinstance(options, list) else []

    if options:
        labels = [str((o.get("label") if isinstance(o, dict) else o) or "").lower() for o in options]
        if all(lbl in {"да", "нет", "yes", "no", "true", "false"} for lbl in labels if lbl):
            return "boolean", None, None
        if any(_parse_range_label(str((o.get("label") if isinstance(o, dict) else o) or "")) for o in options):
            return "numeric_or_option", {"type": "match_numeric_to_option_label"}, None
        return "single_choice", None, None

    if "возраст" in text or "age" in text:
        return "numeric_or_text", None, {"min_value": 0, "max_value": 120}
    if "индекс массы тела" in text or "имт" in text or "bmi" in text:
        return "numeric_or_text", None, {"min_value": 10, "max_value": 100}
    if "талии" in text or "waist" in text:
        return "numeric_or_text", None, {"min_value": 20, "max_value": 300}

    return "free_text", None, None


def graph_meta(runtime_graph: dict[str, Any], language: str) -> dict[str, Any]:
    title = localize_text(runtime_graph.get("title"), language) or runtime_graph.get("topic") or "assessment"
    topic = runtime_graph.get("topic") or title
    questions_count = len([n for n in runtime_graph.get("nodes", []) if isinstance(n, dict) and n.get("type") == "question"])
    return {"title": title, "topic": topic, "questions_count": questions_count}


def create_assessment_state(runtime_graph: dict[str, Any], language: str) -> dict[str, Any]:
    return {
        "status": "idle",
        "language": language,
        "current_node_id": runtime_graph.get("entry_node_id"),
        "answers": [],
        "score_total": 0.0,
        "result": None,
    }


def get_node_map(runtime_graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    node_map: dict[str, dict[str, Any]] = {}
    for node in runtime_graph.get("nodes", []):
        if isinstance(node, dict) and node.get("id"):
            node_map[str(node["id"])] = node
    return node_map


def get_current_node(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> dict[str, Any] | None:
    node_map = get_node_map(runtime_graph)
    node_id = assessment_state.get("current_node_id")
    if not isinstance(node_id, str):
        return None
    return node_map.get(node_id)


def start_assessment(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> dict[str, Any]:
    assessment_state["status"] = "in_progress"
    node = get_current_node(runtime_graph, assessment_state)
    if not node:
        return {"reply_text": _localized_text({"ru": "Сейчас нет доступного вопроса.", "en": "There is no available question right now."}, assessment_state["language"]), "assessment_state": assessment_state}
    return render_node_prompt(runtime_graph, assessment_state, node)


def render_node_prompt(runtime_graph: dict[str, Any], assessment_state: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    language = assessment_state["language"]

    if node.get("type") == "question":
        questions = [n for n in runtime_graph.get("nodes", []) if isinstance(n, dict) and n.get("type") == "question"]
        question_ids = [str(q.get("id")) for q in questions]
        current_id = str(node.get("id"))
        idx = question_ids.index(current_id) if current_id in question_ids else 0

        text = _localized_text(node.get("text"), language, fallback="Question")
        parts = [f"{'Вопрос' if language == 'ru' else 'Question'} {idx + 1}/{len(questions)}: {text}"]

        options = node.get("options", [])
        if isinstance(options, list) and options:
            parts.append("")
            parts.append("Варианты ответа:" if language == "ru" else "Answer options:")
            for i, option in enumerate(options, start=1):
                if isinstance(option, dict):
                    parts.append(f"{i}. {option.get('label', '—')}")
            parts.append("")
            parts.append(
                "Можно ответить номером, текстом варианта или своими словами — я постараюсь понять смысл."
                if language == "ru"
                else "You can answer with the option number, the option text, or in your own words — I will try to understand the meaning."
            )
        else:
            parts.append("")
            parts.append(
                "Можете ответить в свободной форме. Если уместно, можно просто написать число."
                if language == "ru"
                else "You can answer in free form. When appropriate, you can just send a number."
            )

        return {"reply_text": "\n".join(parts), "assessment_state": assessment_state}

    if node.get("type") in {"result", "terminal"}:
        return build_result(runtime_graph, assessment_state)

    return {"reply_text": _localized_text(node.get("text"), language, fallback=""), "assessment_state": assessment_state}


def explain_current_question(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> str:
    node = get_current_node(runtime_graph, assessment_state)
    if not node:
        return _localized_text({"ru": "Сейчас у меня нет активного вопроса.", "en": "I do not have an active question right now."}, assessment_state["language"])

    why = _localized_text(node.get("why_it_matters"), assessment_state["language"])
    if why:
        return why

    return _localized_text(
        {"ru": "Этот вопрос помогает точнее определить итог assessment.", "en": "This question helps make the assessment result more accurate."},
        assessment_state["language"],
    )


def help_with_current_question(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> str:
    node = get_current_node(runtime_graph, assessment_state)
    if not node:
        return _localized_text({"ru": "Сейчас у меня нет активного вопроса.", "en": "I do not have an active question right now."}, assessment_state["language"])

    help_text = _localized_text(node.get("help_text"), assessment_state["language"])
    if help_text:
        return help_text

    return _localized_text(
        {"ru": "Вы можете ответить своими словами, а я постараюсь привести ответ к нужному формату.", "en": "You can answer in your own words, and I will try to normalize it into the expected format."},
        assessment_state["language"],
    )


def repeat_current_question(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> str:
    node = get_current_node(runtime_graph, assessment_state)
    if not node:
        return _localized_text({"ru": "Сейчас у меня нет активного вопроса.", "en": "I do not have an active question right now."}, assessment_state["language"])
    rendered = render_node_prompt(runtime_graph, assessment_state, node)
    return rendered["reply_text"]


def infer_answer_deterministically(node: dict[str, Any], user_message: str, language: str) -> dict[str, Any]:
    text = user_message.strip()
    low = _normalize(text)
    options = node.get("options", [])
    options = options if isinstance(options, list) else []
    question_type = node.get("question_type", "single_choice")

    yes_no = normalize_yes_no(text)
    if yes_no is not None:
        if options:
            match = _match_yes_no_to_option(options, yes_no)
            if match:
                return {
                    "ok": True,
                    "raw_answer": user_message,
                    "value": match.get("value", yes_no),
                    "selected_option": match.get("label"),
                    "score": float(match.get("score", 0.0)),
                }
        if question_type == "boolean":
            return {"ok": True, "raw_answer": user_message, "value": yes_no, "selected_option": None, "score": 0.0}

    if options:
        by_index = _match_option_by_index(options, low)
        if by_index:
            return {"ok": True, "raw_answer": user_message, "value": by_index.get("value"), "selected_option": by_index.get("label"), "score": float(by_index.get("score", 0.0))}
        by_label = _match_option_by_label(options, low)
        if by_label:
            return {"ok": True, "raw_answer": user_message, "value": by_label.get("value"), "selected_option": by_label.get("label"), "score": float(by_label.get("score", 0.0))}

    numeric = _extract_float(text)
    if numeric is not None:
        validation_rule = node.get("validation_rule")
        if isinstance(validation_rule, dict):
            min_value = validation_rule.get("min_value")
            max_value = validation_rule.get("max_value")
            if min_value is not None and numeric < float(min_value):
                return {"ok": False, "raw_answer": user_message}
            if max_value is not None and numeric > float(max_value):
                return {"ok": False, "raw_answer": user_message}

        normalization_rule = node.get("normalization_rule")
        if isinstance(normalization_rule, dict) and normalization_rule.get("type") == "match_numeric_to_option_label" and options:
            matched = _match_numeric_to_option_label(options, numeric)
            if matched:
                return {
                    "ok": True,
                    "raw_answer": user_message,
                    "value": matched.get("value"),
                    "selected_option": matched.get("label"),
                    "score": float(matched.get("score", 0.0)),
                }

        if question_type in {"numeric_or_text", "numeric_or_option", "numeric", "number"}:
            return {"ok": True, "raw_answer": user_message, "value": numeric, "selected_option": None, "score": 0.0}

    if question_type in {"free_text", "text", "numeric_or_text"}:
        return {"ok": True, "raw_answer": user_message, "value": text, "selected_option": None, "score": 0.0}

    return {"ok": False, "raw_answer": user_message}


def answer_current_question(runtime_graph: dict[str, Any], assessment_state: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    node = get_current_node(runtime_graph, assessment_state)
    language = assessment_state["language"]

    if not node:
        return {"reply_text": _localized_text({"ru": "Сейчас нет активного вопроса.", "en": "There is no active question right now."}, language), "assessment_state": assessment_state, "completed": False}

    if not normalized.get("ok"):
        prompt = repeat_current_question(runtime_graph, assessment_state)
        reply = (
            "Я не смог понять ответ. Давайте попробуем ещё раз.\n\n" + prompt
            if language == "ru"
            else "I could not understand that answer. Let's try again.\n\n" + prompt
        )
        return {"reply_text": reply, "assessment_state": assessment_state, "completed": False}

    answer_record = {
        "node_id": node.get("id"),
        "question_text": _localized_text(node.get("text"), language, fallback=str(node.get("id"))),
        "raw_answer": normalized.get("raw_answer"),
        "normalized_value": normalized.get("value"),
        "selected_option": normalized.get("selected_option"),
        "score": float(normalized.get("score", 0.0)),
    }
    assessment_state["answers"].append(answer_record)
    assessment_state["score_total"] = float(assessment_state.get("score_total", 0.0)) + float(normalized.get("score", 0.0))

    next_node_id = resolve_next_node_id(node, normalized)
    if not next_node_id:
        result = build_result(runtime_graph, assessment_state)
        return {"reply_text": result["reply_text"], "assessment_state": result["assessment_state"], "completed": True}

    assessment_state["current_node_id"] = next_node_id
    next_node = get_current_node(runtime_graph, assessment_state)
    if not next_node or next_node.get("type") in {"result", "terminal"}:
        result = build_result(runtime_graph, assessment_state)
        return {"reply_text": result["reply_text"], "assessment_state": result["assessment_state"], "completed": True}

    rendered = render_node_prompt(runtime_graph, assessment_state, next_node)
    return {"reply_text": rendered["reply_text"], "assessment_state": rendered["assessment_state"], "completed": False}


def resolve_next_node_id(node: dict[str, Any], normalized: dict[str, Any]) -> str | None:
    next_map = node.get("next", {})
    if not isinstance(next_map, dict):
        return None

    selected = normalized.get("selected_option")
    normalized_value = str(normalized.get("value")).lower() if normalized.get("value") is not None else None

    if isinstance(selected, str):
        if selected in next_map:
            return next_map[selected]
        low_selected = selected.lower()
        if low_selected in next_map:
            return next_map[low_selected]

    if normalized_value and normalized_value in next_map:
        return next_map[normalized_value]

    return next_map.get("default")


def build_result(runtime_graph: dict[str, Any], assessment_state: dict[str, Any]) -> dict[str, Any]:
    language = assessment_state["language"]
    score_total = float(assessment_state.get("score_total", 0.0))
    risk_band = find_risk_band(score_total, runtime_graph.get("risk_bands", []))
    meta = graph_meta(runtime_graph, language)

    assessment_state["status"] = "completed"
    assessment_state["result"] = {
        "score_total": score_total,
        "risk_band": risk_band,
        "graph_title": meta["title"],
        "topic": meta["topic"],
    }

    if language == "ru":
        if risk_band:
            label = risk_band.get("label", "неизвестно")
            reply_text = (
                f"Спасибо, assessment завершён.\n\n"
                f"Тема: {meta['title']}\n"
                f"Суммарный балл: {score_total:g}\n"
                f"Категория результата: {label}\n\n"
                f"Если хотите, я могу кратко объяснить результат или помочь подобрать другой assessment."
            )
        else:
            reply_text = (
                f"Спасибо, assessment завершён.\n\n"
                f"Тема: {meta['title']}\n"
                f"Суммарный балл: {score_total:g}\n\n"
                f"Если хотите, я могу кратко объяснить результат или помочь подобрать другой assessment."
            )
    else:
        if risk_band:
            label = risk_band.get("label", "unknown")
            reply_text = (
                f"Thank you, the assessment is complete.\n\n"
                f"Topic: {meta['title']}\n"
                f"Total score: {score_total:g}\n"
                f"Result category: {label}\n\n"
                f"If you want, I can briefly explain the result or help choose another assessment."
            )
        else:
            reply_text = (
                f"Thank you, the assessment is complete.\n\n"
                f"Topic: {meta['title']}\n"
                f"Total score: {score_total:g}\n\n"
                f"If you want, I can briefly explain the result or help choose another assessment."
            )

    return {"reply_text": reply_text, "assessment_state": assessment_state}


def find_risk_band(score_total: float, risk_bands: list[dict[str, Any]]) -> dict[str, Any] | None:
    for band in risk_bands:
        if not isinstance(band, dict):
            continue
        try:
            min_score = float(band.get("min_score"))
            max_score = float(band.get("max_score"))
        except Exception:
            continue
        if min_score <= score_total <= max_score:
            return band
    return None


def normalize_yes_no(message: str) -> bool | None:
    low = _normalize(message)
    if low in YES_WORDS_RU or low in YES_WORDS_EN:
        return True
    if low in NO_WORDS_RU or low in NO_WORDS_EN:
        return False
    return None


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _match_yes_no_to_option(options: list[dict[str, Any]], yes_no: bool) -> dict[str, Any] | None:
    target_words = {"да", "yes", "true"} if yes_no else {"нет", "no", "false"}
    for option in options:
        label = _normalize(str(option.get("label", "")))
        if label in target_words:
            return option
    return None


def _match_option_by_index(options: list[dict[str, Any]], low: str) -> dict[str, Any] | None:
    if not low.isdigit():
        return None
    idx = int(low) - 1
    if 0 <= idx < len(options):
        return options[idx]
    return None


def _match_option_by_label(options: list[dict[str, Any]], low: str) -> dict[str, Any] | None:
    for option in options:
        label = _normalize(str(option.get("label", "")))
        if label == low:
            return option
    for option in options:
        label = _normalize(str(option.get("label", "")))
        if low and low in label:
            return option
    return None


def _extract_float(text: str) -> float | None:
    match = re.search(r"(-?\d+(?:[.,]\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except Exception:
        return None


def _normalize_options(options: Any) -> list[dict[str, Any]]:
    if not isinstance(options, list):
        return []

    normalized: list[dict[str, Any]] = []
    for idx, option in enumerate(options):
        if isinstance(option, str):
            normalized.append({"id": f"opt_{idx + 1}", "label": option, "value": option, "score": 0.0})
            continue
        if not isinstance(option, dict):
            continue
        label = option.get("label") or option.get("text") or option.get("value") or f"Option {idx + 1}"
        normalized.append(
            {
                "id": str(option.get("id") or f"opt_{idx + 1}"),
                "label": label,
                "value": option.get("value", label),
                "score": float(option.get("score", 0.0)) if option.get("score") is not None else 0.0,
                "notes": option.get("notes"),
            }
        )
    return normalized


def _default_help_for_question(question: dict[str, Any], q_type: str) -> dict[str, str] | str | None:
    if q_type in {"numeric_or_text", "numeric_or_option"}:
        return {
            "ru": "Можно ответить числом, например 30 или 27.5. Я постараюсь сам привести ответ к нужному формату.",
            "en": "You can answer with a number, for example 30 or 27.5. I will try to normalize it to the expected format.",
        }
    options = question.get("options")
    if isinstance(options, list) and options:
        return {
            "ru": "Можно ответить номером варианта, текстом варианта или своими словами, если смысл совпадает.",
            "en": "You can answer with the option number, the option text, or in your own words if the meaning matches.",
        }
    return {
        "ru": "Ответьте так, как вам удобнее. Если нужно, я помогу уточнить формат.",
        "en": "Answer in the way that feels easiest. If needed, I can help clarify the format.",
    }


def _first_node_id(nodes: list[Any]) -> str | None:
    for node in nodes:
        if isinstance(node, dict) and node.get("id"):
            return str(node["id"])
    return None


def _normalize_nodes(nodes: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for idx, raw in enumerate(nodes):
        if not isinstance(raw, dict):
            continue
        q_type, normalization_rule, validation_rule = infer_runtime_rules(raw)
        normalized.append(
            {
                "id": str(raw.get("id") or f"node_{idx + 1}"),
                "type": raw.get("type", "question"),
                "question_type": raw.get("question_type", q_type),
                "text": raw.get("text", f"Node {idx + 1}"),
                "help_text": raw.get("help_text"),
                "why_it_matters": raw.get("why_it_matters"),
                "options": _normalize_options(raw.get("options")),
                "normalization_rule": raw.get("normalization_rule") or normalization_rule,
                "validation_rule": raw.get("validation_rule") or validation_rule,
                "scoring_rule": raw.get("scoring_rule") or {"type": "selected_option_score"},
                "next": raw.get("next", {}) if isinstance(raw.get("next"), dict) else {},
            }
        )
    return normalized


def _match_numeric_to_option_label(options: list[dict[str, Any]], value: float) -> dict[str, Any] | None:
    for option in options:
        label = str(option.get("label", "")).strip()
        parsed = _parse_range_label(label)
        if not parsed:
            continue

        kind = parsed["kind"]
        if kind == "lt" and value < parsed["max"]:
            return option
        if kind == "gt" and value > parsed["min"]:
            return option
        if kind == "ge" and value >= parsed["min"]:
            return option
        if kind == "range" and parsed["min"] <= value <= parsed["max"]:
            return option
    return None


def _parse_range_label(label: str) -> dict[str, Any] | None:
    normalized = label.replace("–", "-").replace("—", "-").replace(" ", "")

    m = re.match(r"^<(\d+(?:[.,]\d+)?)", normalized)
    if m:
        return {"kind": "lt", "max": float(m.group(1).replace(",", "."))}

    m = re.match(r"^>(\d+(?:[.,]\d+)?)", normalized)
    if m:
        return {"kind": "gt", "min": float(m.group(1).replace(",", "."))}

    m = re.match(r"^(\d+(?:[.,]\d+)?)\+$", normalized)
    if m:
        return {"kind": "ge", "min": float(m.group(1).replace(",", "."))}

    m = re.match(r"^(\d+(?:[.,]\d+)?)-(\d+(?:[.,]\d+)?)", normalized)
    if m:
        return {"kind": "range", "min": float(m.group(1).replace(",", ".")), "max": float(m.group(2).replace(",", "."))}

    return None


def _localized_text(value: Any, language: str, fallback: str = "") -> str:
    return localize_text(value, language, fallback)
EOF

write_file "agents/patient_controller/app.py" <<'EOF'
import json
from typing import Any

from fastapi import FastAPI

from shared.config import get_settings
from shared.graph_registry import get_graph_record, list_graph_summaries, search_graphs
from shared.patient_graph_runtime import (
    answer_current_question,
    create_assessment_state,
    detect_language,
    explain_current_question,
    extract_runtime_graph,
    get_current_node,
    graph_meta,
    help_with_current_question,
    infer_answer_deterministically,
    repeat_current_question,
    start_assessment,
)
from shared.patient_session_store import load_session, save_session
from shared.together_client import TogetherAIClient

app = FastAPI(title="Patient Controller", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "patient-controller"}


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _detect_language_switch(message: str) -> str | None:
    low = _normalize(message)
    if "русск" in low or "на русском" in low or "по-русски" in low:
        return "ru"
    if "english" in low or "speak english" in low or "in english" in low:
        return "en"
    return None


def _is_greeting(message: str) -> bool:
    low = _normalize(message)
    return low in {"привет", "здравствуй", "здравствуйте", "hello", "hi", "hey"}


def _consent_from_message(message: str) -> str | None:
    low = _normalize(message)
    yes_words = {"да", "ок", "окей", "поехали", "начать", "давай", "хочу", "yes", "ok", "okay", "sure", "start", "let's start"}
    no_words = {"нет", "не хочу", "пока нет", "not now", "no", "later"}

    if low in yes_words:
        return "accepted"
    if low in no_words:
        return "declined"
    return None


def _looks_like_capabilities(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["что умеешь", "что ты умеешь", "что еще умеешь", "кроме", "what can you do", "what else can you do", "capabilities"])


def _looks_like_explain_assessment(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["что это", "что за тест", "что это за тест", "зачем этот тест", "what is this", "what is this test"])


def _looks_like_why_question(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["зачем этот вопрос", "почему этот вопрос", "why this question", "why do you ask"])


def _looks_like_help(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["не понял", "помоги", "help", "как отвечать", "не знаю", "что писать"])


def _looks_like_repeat(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["повтори", "ещё раз", "repeat", "again"])


def _looks_like_pause(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["пауза", "pause", "потом", "later", "останов", "stop for now"])


def _looks_like_resume(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["продолж", "resume", "continue", "дальше"])


def _looks_like_result_request(message: str) -> bool:
    low = _normalize(message)
    return any(token in low for token in ["результат", "итог", "summary", "result"])


def _default_session(conversation_id: str, language: str) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "mode": "free_conversation",
        "language": language,
        "discovered_graphs": [],
        "selected_graph_id": None,
        "consent_status": None,
        "assessment_state": None,
        "last_result": None,
        "history": [],
    }


def _capabilities_text(language: str) -> str:
    graphs = list_graph_summaries(limit=8)
    if not graphs:
        return (
            "Сейчас в библиотеке графов пока нет опубликованных assessments."
            if language == "ru"
            else "There are no published assessments in the graph library yet."
        )

    lines = []
    if language == "ru":
        lines.append("Я могу помочь подобрать и провести assessment из доступной библиотеки графов.")
        lines.append("")
        lines.append("Сейчас доступны такие assessments:")
        for item in graphs[:5]:
            lines.append(
                f"- {item.get('title')} ({item.get('questions_count', '?')} вопросов, ~{item.get('estimated_time_minutes', '?')} мин)"
            )
        lines.append("")
        lines.append("Если опишете свой запрос, цель или проблему, я постараюсь подобрать наиболее подходящий assessment.")
    else:
        lines.append("I can help choose and run an assessment from the available graph library.")
        lines.append("")
        lines.append("Right now these assessments are available:")
        for item in graphs[:5]:
            lines.append(
                f"- {item.get('title')} ({item.get('questions_count', '?')} questions, ~{item.get('estimated_time_minutes', '?')} min)"
            )
        lines.append("")
        lines.append("If you describe your concern, goal, or problem, I will try to find the most relevant assessment.")

    return "\n".join(lines)


def _greeting_text(language: str) -> str:
    if language == "ru":
        return (
            "Привет. Я могу пообщаться с вами в свободной форме, помочь разобраться с запросом и, если это уместно, подобрать assessment из моей библиотеки.\n\n"
            "Можете просто рассказать, что вас беспокоит или что вы хотите оценить."
        )
    return (
        "Hi. I can talk with you freely, help understand your request, and, when relevant, select an assessment from my library.\n\n"
        "You can simply describe what is bothering you or what you would like to evaluate."
    )


def _offer_text(candidate: dict[str, Any], language: str) -> str:
    metadata = candidate.get("metadata", {}) or {}
    title = metadata.get("title") or candidate.get("graph_id")
    description = metadata.get("description") or ""
    questions_count = metadata.get("questions_count") or "?"
    duration = metadata.get("estimated_time_minutes") or "?"

    if language == "ru":
        return (
            f"По вашему описанию вам может подойти assessment «{title}».\n"
            f"{description}\n"
            f"Это примерно {questions_count} вопросов и около {duration} минут.\n\n"
            f"Хотите пройти его сейчас?"
        )
    return (
        f"Based on what you described, a suitable assessment may be “{title}”.\n"
        f"{description}\n"
        f"It is about {questions_count} questions and around {duration} minutes.\n\n"
        f"Would you like to take it now?"
    )


def _no_match_text(language: str) -> str:
    if language == "ru":
        return (
            "Я пока не нашёл явно подходящий assessment по этому описанию.\n"
            "Можете рассказать чуть подробнее, что именно вы хотите оценить, или спросить, какие assessments сейчас доступны."
        )
    return (
        "I have not found a clearly suitable assessment for that description yet.\n"
        "You can tell me a bit more about what you want to evaluate, or ask which assessments are currently available."
    )


def _decline_text(language: str) -> str:
    if language == "ru":
        return "Хорошо, не будем запускать assessment сейчас. Можете продолжать свободный диалог, и я помогу подобрать другой вариант, если нужно."
    return "Okay, we do not have to start the assessment right now. You can continue the conversation freely, and I can help find another option if needed."


def _result_text(result: dict[str, Any] | None, language: str) -> str:
    if not isinstance(result, dict):
        return (
            "Assessment ещё не завершён. Если хотите, можем продолжить."
            if language == "ru"
            else "The assessment is not completed yet. If you want, we can continue."
        )

    risk_band = result.get("risk_band") or {}
    if language == "ru":
        return (
            f"Тема: {result.get('graph_title')}\n"
            f"Суммарный балл: {result.get('score_total')}\n"
            f"Категория: {risk_band.get('label', '—')}"
        )
    return (
        f"Topic: {result.get('graph_title')}\n"
        f"Total score: {result.get('score_total')}\n"
        f"Category: {risk_band.get('label', '—')}"
    )


async def _llm_map_answer(node: dict[str, Any], message: str, language: str) -> dict[str, Any]:
    settings = get_settings()
    llm = TogetherAIClient(model=settings.patient_controller_model)

    system_prompt = (
        "You are an answer normalizer for a conversational assessment assistant.\n"
        "Map the user's free-form answer to the current graph node.\n\n"
        "Return only valid JSON with keys:\n"
        "- ok\n"
        "- value\n"
        "- selected_option\n"
        "- score\n\n"
        "If the answer cannot be mapped safely, return {\"ok\": false}.\n"
    )

    user_prompt = json.dumps(
        {
            "language": language,
            "node": {
                "id": node.get("id"),
                "question_type": node.get("question_type"),
                "text": node.get("text"),
                "help_text": node.get("help_text"),
                "options": node.get("options"),
                "normalization_rule": node.get("normalization_rule"),
                "validation_rule": node.get("validation_rule"),
            },
            "user_reply": message,
        },
        ensure_ascii=False,
        indent=2,
    )

    try:
        result = await llm.complete_json(system_prompt=system_prompt, user_prompt=user_prompt)
    except Exception:
        result = None

    if not isinstance(result, dict):
        return {"ok": False, "raw_answer": message}

    if not result.get("ok"):
        return {"ok": False, "raw_answer": message}

    try:
        score = float(result.get("score", 0.0))
    except Exception:
        score = 0.0

    selected_option = result.get("selected_option")
    return {
        "ok": True,
        "raw_answer": message,
        "value": result.get("value"),
        "selected_option": selected_option if isinstance(selected_option, str) else None,
        "score": score,
    }


async def _find_graph_candidates(message: str, language: str) -> list[dict[str, Any]]:
    candidates = search_graphs(message, top_k=5)
    return candidates


@app.post("/chat")
async def chat(payload: dict[str, Any]) -> dict[str, Any]:
    conversation_id = str(payload.get("conversation_id") or "unknown_conversation")
    user_message = str(payload.get("user_message") or "").strip()

    if not user_message:
        return {"status": "error", "reply_text": "Empty message", "session_state": {}}

    session = load_session(conversation_id)
    if not isinstance(session, dict):
        session = _default_session(conversation_id, detect_language(user_message))

    maybe_lang = _detect_language_switch(user_message)
    if maybe_lang:
        session["language"] = maybe_lang
    language = session["language"]

    mode = session.get("mode", "free_conversation")
    reply_text = ""

    if user_message == "/start":
        reply_text = _greeting_text(language)

    elif _looks_like_capabilities(user_message):
        reply_text = _capabilities_text(language)

    elif mode == "awaiting_consent":
        consent = _consent_from_message(user_message)
        if consent == "accepted":
            graph_id = session.get("selected_graph_id")
            record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
            runtime_graph = extract_runtime_graph(record)
            assessment_state = create_assessment_state(runtime_graph, language)
            rendered = start_assessment(runtime_graph, assessment_state)
            session["assessment_state"] = rendered["assessment_state"]
            session["mode"] = "assessment_in_progress"
            session["consent_status"] = "accepted"
            reply_text = rendered["reply_text"]
        elif consent == "declined":
            session["mode"] = "free_conversation"
            session["consent_status"] = "declined"
            session["selected_graph_id"] = None
            reply_text = _decline_text(language)
        else:
            graph_id = session.get("selected_graph_id")
            record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
            if record:
                reply_text = _offer_text(
                    {
                        "graph_id": record.get("graph_id"),
                        "metadata": record.get("metadata", {}),
                    },
                    language,
                )
            else:
                session["mode"] = "free_conversation"
                reply_text = _no_match_text(language)

    elif mode == "assessment_in_progress":
        graph_id = session.get("selected_graph_id")
        record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
        runtime_graph = extract_runtime_graph(record)
        assessment_state = session.get("assessment_state")
        if not isinstance(assessment_state, dict):
            assessment_state = create_assessment_state(runtime_graph, language)
            session["assessment_state"] = assessment_state

        if _looks_like_pause(user_message):
            session["mode"] = "paused_assessment"
            reply_text = (
                "Хорошо, поставим assessment на паузу. Когда захотите продолжить, просто напишите мне."
                if language == "ru"
                else "Okay, we can pause the assessment here. When you want to continue, just send me a message."
            )
        elif maybe_lang:
            assessment_state["language"] = language
            session["assessment_state"] = assessment_state
            ack = "Хорошо, продолжим по-русски.\n\n" if language == "ru" else "Okay, we will continue in English.\n\n"
            reply_text = ack + repeat_current_question(runtime_graph, assessment_state)
        elif _is_greeting(user_message):
            reply_text = (
                "Привет. Мы сейчас находимся внутри assessment. Если хотите, можем продолжить с текущего вопроса.\n\n"
                + repeat_current_question(runtime_graph, assessment_state)
                if language == "ru"
                else "Hi. We are currently inside the assessment. If you want, we can continue from the current question.\n\n"
                + repeat_current_question(runtime_graph, assessment_state)
            )
        elif _looks_like_why_question(user_message):
            reply_text = explain_current_question(runtime_graph, assessment_state) + "\n\n" + repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_help(user_message):
            reply_text = help_with_current_question(runtime_graph, assessment_state) + "\n\n" + repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_repeat(user_message):
            reply_text = repeat_current_question(runtime_graph, assessment_state)
        elif _looks_like_result_request(user_message):
            reply_text = _result_text(assessment_state.get("result"), language)
        elif _looks_like_capabilities(user_message):
            reply_text = (
                "Сейчас мы проходим один assessment. Я могу продолжить его, поставить на паузу или позже помочь подобрать другой graph."
                if language == "ru"
                else "We are currently going through one assessment. I can continue it, pause it, or later help choose another graph."
            )
        else:
            node = get_current_node(runtime_graph, assessment_state)
            deterministic = infer_answer_deterministically(node or {}, user_message, language)
            normalized = deterministic
            if not deterministic.get("ok") and isinstance(node, dict):
                normalized = await _llm_map_answer(node, user_message, language)
            result = answer_current_question(runtime_graph, assessment_state, normalized)
            session["assessment_state"] = result["assessment_state"]
            reply_text = result["reply_text"]
            if result.get("completed"):
                session["mode"] = "post_assessment"
                session["last_result"] = (result["assessment_state"] or {}).get("result")

    elif mode == "paused_assessment":
        if _looks_like_resume(user_message) or _consent_from_message(user_message) == "accepted":
            session["mode"] = "assessment_in_progress"
            graph_id = session.get("selected_graph_id")
            record = get_graph_record(graph_id) if isinstance(graph_id, str) else None
            runtime_graph = extract_runtime_graph(record)
            assessment_state = session.get("assessment_state")
            if not isinstance(assessment_state, dict):
                assessment_state = create_assessment_state(runtime_graph, language)
                session["assessment_state"] = assessment_state
            assessment_state["language"] = language
            reply_text = repeat_current_question(runtime_graph, assessment_state)
        else:
            reply_text = (
                "Сейчас assessment на паузе. Когда захотите продолжить, просто скажите об этом."
                if language == "ru"
                else "The assessment is currently paused. When you want to continue, just tell me."
            )

    else:
        if _looks_like_result_request(user_message):
            reply_text = _result_text(session.get("last_result"), language)
        elif _looks_like_explain_assessment(user_message):
            reply_text = (
                "Я могу помочь подобрать assessment из библиотеки графов, предложить наиболее подходящий вариант и провести вас по нему шаг за шагом."
                if language == "ru"
                else "I can help select an assessment from the graph library, suggest the most relevant option, and guide you through it step by step."
            )
        elif _is_greeting(user_message):
            reply_text = _greeting_text(language)
        else:
            candidates = await _find_graph_candidates(user_message, language)
            if candidates:
                top = candidates[0]
                if float(top.get("score", 0.0)) >= 3.0:
                    session["mode"] = "awaiting_consent"
                    session["selected_graph_id"] = top.get("graph_id")
                    session["discovered_graphs"] = [c.get("graph_id") for c in candidates if c.get("graph_id")]
                    session["consent_status"] = "pending"
                    reply_text = _offer_text(top, language)
                else:
                    reply_text = _no_match_text(language)
            else:
                reply_text = _no_match_text(language)

    history = session.get("history", [])
    if not isinstance(history, list):
        history = []
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": reply_text})
    session["history"] = history[-20:]
    save_session(conversation_id, session)

    return {
        "status": session.get("mode", "free_conversation"),
        "reply_text": reply_text,
        "session_state": session,
    }
EOF

write_file "agents/compiler_agent/app.py" <<'EOF'
import hashlib
import re

from fastapi import FastAPI

from shared.schemas import CompileRequest, CompileResponse

app = FastAPI(title="Compiler Agent", version="0.3.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "compiler-agent"}


def _missing_feedback(draft: dict) -> list[str]:
    feedback: list[str] = []

    understood = draft.get("understood", {}) or {}
    if not understood.get("topic"):
        feedback.append("Topic is missing")

    questions = draft.get("candidate_questions", []) or []
    if not questions:
        feedback.append("At least one question is required")

    scoring = draft.get("candidate_scoring_rules", {}) or {}
    if not scoring.get("method"):
        feedback.append("Scoring logic is missing")

    return feedback


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "assessment"


def _build_graph_id(topic: str, questions: list[dict]) -> str:
    seed = topic + "|" + "|".join(str(q.get("text", "")) for q in questions if isinstance(q, dict))
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"{_slugify(topic)}_{digest}"


@app.post("/compile", response_model=CompileResponse)
async def compile_graph(payload: CompileRequest) -> CompileResponse:
    draft = payload.draft or {}
    feedback = _missing_feedback(draft)

    if feedback:
        return CompileResponse(
            status="invalid",
            graph_version_id=None,
            graph=None,
            feedback=feedback,
        )

    understood = draft.get("understood", {}) or {}
    topic = understood.get("topic", "assessment")
    title = topic.replace("_", " ").title()

    questions = draft.get("candidate_questions", []) or []
    graph_id = _build_graph_id(str(topic), questions)

    graph = {
        "graph_version_id": graph_id,
        "title": title,
        "topic": topic,
        "target_audience": understood.get("target_audience"),
        "questions": questions,
        "risk_bands": draft.get("candidate_risk_bands", []) or [],
        "scoring": draft.get("candidate_scoring_rules", {}) or {},
        "report_rules": draft.get("candidate_report_requirements", []) or [],
        "safety_rules": draft.get("candidate_safety_requirements", []) or [],
        "source_draft": draft,
    }

    return CompileResponse(
        status="compiled",
        graph_version_id=graph_id,
        graph=graph,
        feedback=[],
    )
EOF

write_file "bots/user_bot/bot.py" <<'EOF'
import asyncio

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from shared.config import get_settings
from shared.http_client import post_json
from shared.graph_registry import list_graph_summaries
from shared.published_graph_store import load_active_graph_record

settings = get_settings()
dp = Dispatcher()


def _graph_library_available() -> bool:
    return len(list_graph_summaries(limit=1)) > 0 or isinstance(load_active_graph_record(), dict)


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    if not _graph_library_available():
        await message.answer(
            "Сейчас библиотека assessment graphs пуста. Сначала опубликуйте хотя бы один graph из specialist bot."
        )
        return

    conversation_id = f"user_conv_{message.chat.id}"
    try:
        result = await post_json(
            f"{settings.patient_controller_url}/chat",
            {"conversation_id": conversation_id, "user_message": "/start"},
        )
    except httpx.HTTPError:
        await message.answer(
            "Patient controller is temporarily unavailable. Please try again in a moment."
        )
        return

    await message.answer(result["reply_text"])


@dp.message(F.text)
async def user_message_handler(message: Message) -> None:
    if not _graph_library_available():
        await message.answer(
            "There are no published graphs in the library yet. Please publish at least one graph from the specialist bot first."
        )
        return

    conversation_id = f"user_conv_{message.chat.id}"

    try:
        result = await post_json(
            f"{settings.patient_controller_url}/chat",
            {"conversation_id": conversation_id, "user_message": message.text},
        )
    except httpx.HTTPError:
        await message.answer(
            "Patient controller is temporarily unavailable. Please try again in a moment."
        )
        return

    await message.answer(result["reply_text"])


async def main() -> None:
    bot = Bot(token=settings.user_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
EOF

write_file ".env.example" <<'EOF'
# Together AI
TOGETHER_API_KEY=your_together_api_key
TOGETHER_MODEL=Qwen/Qwen3.5-9B

# Per-role models
SPECIALIST_CONTROLLER_MODEL=zai-org/GLM-5
PATIENT_CONTROLLER_MODEL=zai-org/GLM-5
DEFINITION_AGENT_MODEL=Qwen/Qwen3.5-397B-A17B
RUNTIME_AGENT_MODEL=Qwen/Qwen3.5-9B
REPORT_AGENT_MODEL=Qwen/Qwen3.5-9B
EVALUATION_AGENT_MODEL=Qwen/Qwen3.5-9B

# Telegram bots
SPECIALIST_BOT_TOKEN=your_specialist_bot_token
USER_BOT_TOKEN=your_user_bot_token

# Internal agent endpoints
DEFINITION_AGENT_URL=http://definition-agent:8000
COMPILER_AGENT_URL=http://compiler-agent:8000
RUNTIME_AGENT_URL=http://runtime-agent:8000
REPORT_AGENT_URL=http://report-agent:8000
EVALUATION_AGENT_URL=http://evaluation-agent:8000
PATIENT_CONTROLLER_URL=http://patient-controller:8000
EOF

write_file "run_patient_controller.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
uv run uvicorn agents.patient_controller.app:app --reload --port 8106
EOF
chmod +x "${ROOT_DIR}/run_patient_controller.sh"
ok "Set executable bit: run_patient_controller.sh"

write_file "docker-compose.yml" <<'EOF'
services:
  definition-agent:
    build:
      context: .
      dockerfile: Dockerfile.agent
      args:
        SERVICE_MODULE: agents.definition_agent.app:app
    env_file:
      - .env
    ports:
      - "8101:8000"

  compiler-agent:
    build:
      context: .
      dockerfile: Dockerfile.agent
      args:
        SERVICE_MODULE: agents.compiler_agent.app:app
    env_file:
      - .env
    ports:
      - "8102:8000"

  runtime-agent:
    build:
      context: .
      dockerfile: Dockerfile.agent
      args:
        SERVICE_MODULE: agents.runtime_agent.app:app
    env_file:
      - .env
    ports:
      - "8103:8000"
    volumes:
      - ./data:/app/data

  report-agent:
    build:
      context: .
      dockerfile: Dockerfile.agent
      args:
        SERVICE_MODULE: agents.report_agent.app:app
    env_file:
      - .env
    ports:
      - "8104:8000"

  evaluation-agent:
    build:
      context: .
      dockerfile: Dockerfile.agent
      args:
        SERVICE_MODULE: agents.evaluation_agent.app:app
    env_file:
      - .env
    ports:
      - "8105:8000"

  patient-controller:
    build:
      context: .
      dockerfile: Dockerfile.agent
      args:
        SERVICE_MODULE: agents.patient_controller.app:app
    env_file:
      - .env
    ports:
      - "8106:8000"
    volumes:
      - ./data:/app/data

  specialist-bot:
    build:
      context: .
      dockerfile: Dockerfile.bot
      args:
        BOT_MODULE: bots.specialist_bot.bot
    env_file:
      - .env
    depends_on:
      - definition-agent
      - compiler-agent
    volumes:
      - ./data:/app/data

  user-bot:
    build:
      context: .
      dockerfile: Dockerfile.bot
      args:
        BOT_MODULE: bots.user_bot.bot
    env_file:
      - .env
    depends_on:
      - patient-controller
    volumes:
      - ./data:/app/data
EOF

log "Running checks..."
for rel in \
  shared/config.py \
  shared/graph_registry.py \
  shared/published_graph_store.py \
  shared/patient_session_store.py \
  shared/patient_graph_runtime.py \
  agents/patient_controller/app.py \
  agents/compiler_agent/app.py \
  bots/user_bot/bot.py \
  .env.example \
  docker-compose.yml \
  run_patient_controller.sh
do
  check_file "$rel"
done

if command -v python3 >/dev/null 2>&1; then
  log "Checking Python syntax..."
  python3 -m py_compile \
    "${ROOT_DIR}/shared/config.py" \
    "${ROOT_DIR}/shared/graph_registry.py" \
    "${ROOT_DIR}/shared/published_graph_store.py" \
    "${ROOT_DIR}/shared/patient_session_store.py" \
    "${ROOT_DIR}/shared/patient_graph_runtime.py" \
    "${ROOT_DIR}/agents/patient_controller/app.py" \
    "${ROOT_DIR}/agents/compiler_agent/app.py" \
    "${ROOT_DIR}/bots/user_bot/bot.py"
  ok "Python syntax check passed"
else
  warn "python3 not found; skipped syntax validation"
fi

log "Patient orchestration patch installed successfully."
ok "Backup available at: ${BACKUP_DIR}"

cat <<TXT

What changed:
- patient bot is no longer tied to one active graph
- added graph library registry with search
- publish now writes both active graph and registry entry
- patient controller now supports:
    - free conversation
    - capabilities listing
    - graph discovery
    - graph offer
    - consent
    - assessment runtime
    - result
    - return to free conversation
- compiler now generates unique graph ids instead of reusing graph_v1_demo

Important:
- to populate the graph library properly, re-compile and re-publish graphs after this patch
- each published graph will now get a stable unique id derived from content

Recommended restart:
  1. cd ${ROOT_DIR}
  2. cp .env.example .env
  3. fill tokens and API key
  4. docker compose down --remove-orphans
  5. docker compose build --no-cache compiler-agent patient-controller user-bot specialist-bot
  6. docker compose up

TXT
