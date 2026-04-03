from __future__ import annotations

import io
import re
from typing import Any


YES_WORDS = {"да", "yes", "y", "ok", "true"}
NO_WORDS = {"нет", "no", "n", "false"}

RU_COMMAND_WORDS = {
    "да",
    "нет",
    "привет",
    "на",
    "русском",
    "покажи",
    "драфт",
    "вопросы",
    "скоринг",
    "риски",
    "компилируй",
    "опубликуй",
    "публикуй",
    "примени",
    "предложение",
}

EN_COMMAND_WORDS = {
    "yes",
    "no",
    "hello",
    "hi",
    "english",
    "show",
    "draft",
    "questions",
    "scoring",
    "risks",
    "compile",
    "publish",
    "apply",
    "proposal",
}


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def detect_language(text: str) -> str:
    return "ru" if re.search(r"[а-яА-ЯёЁ]", text) else "en"


def infer_turn_language(text: str, fallback: str = "en") -> str:
    stripped = text.strip()
    if not stripped:
        return fallback
    if re.search(r"[а-яА-ЯёЁ]", stripped):
        return "ru"
    if re.search(r"[a-zA-Z]", stripped):
        low_tokens = set(re.findall(r"[a-zA-Z]+", stripped.lower()))
        if low_tokens & EN_COMMAND_WORDS:
            return "en"
        return "en"
    low_tokens = set(re.findall(r"[0-9_]+|[^\W_]+", stripped.lower(), flags=re.UNICODE))
    if low_tokens & RU_COMMAND_WORDS:
        return "ru"
    if low_tokens & EN_COMMAND_WORDS:
        return "en"
    return fallback


def create_assessment_state(graph: dict[str, Any], language: str) -> dict[str, Any]:
    return {
        "status": "in_progress",
        "language": language,
        "question_index": 0,
        "answers": [],
        "score_total": 0.0,
        "result": None,
    }


def _graph_questions(graph: dict[str, Any]) -> list[dict[str, Any]]:
    questions = graph.get("questions", []) or []
    if questions:
        return questions
    if graph.get("artifact_type") == "clinical_rule_graph":
        return [
            {
                "id": f"input_{idx + 1}",
                "text": str(item),
                "question_type": "number",
                "options": [],
                "source": "runtime synthetic input",
            }
            for idx, item in enumerate(graph.get("diagnostic_inputs", []) or [])
        ]
    return []


def get_current_question(graph: dict[str, Any], assessment_state: dict[str, Any]) -> dict[str, Any] | None:
    questions = _graph_questions(graph)
    idx = int(assessment_state.get("question_index", 0))
    if 0 <= idx < len(questions):
        return questions[idx]
    return None


def _question_index_by_id(graph: dict[str, Any], question_id: str | None) -> int | None:
    if not question_id:
        return None
    for idx, question in enumerate(_graph_questions(graph)):
        if str(question.get("id") or "") == question_id:
            return idx
    return None


def render_question(graph: dict[str, Any], assessment_state: dict[str, Any]) -> str:
    q = get_current_question(graph, assessment_state)
    language = assessment_state.get("language", "ru")
    if not q:
        return "Нет активного вопроса." if language == "ru" else "There is no active question."

    idx = int(assessment_state.get("question_index", 0))
    total = len(_graph_questions(graph))
    lines = [f"{'Вопрос' if language == 'ru' else 'Question'} {idx + 1}/{total}: {q.get('text', '—')}"]

    options = q.get("options", [])
    if options:
        lines.append("")
        lines.append("Варианты ответа:" if language == "ru" else "Answer options:")
        for i, option in enumerate(options, start=1):
            lines.append(f"{i}. {option.get('label', '—')}")
        lines.append("")
        lines.append(
            "Можно ответить номером или текстом варианта."
            if language == "ru"
            else "You can answer with the option number or the option text."
        )
    elif str(q.get("question_type") or "") == "number":
        lines.append("")
        lines.append("Введите число." if language == "ru" else "Enter a number.")
    return "\n".join(lines)


def explain_result(result: dict[str, Any] | None, language: str) -> str:
    if not isinstance(result, dict):
        return "Нет результата для объяснения." if language == "ru" else "There is no result to explain."

    risk_band = result.get("risk_band") or {}
    label = risk_band.get("label", "—")
    meaning = risk_band.get("meaning")
    if language == "ru":
        text = f"По опроснику «{result.get('graph_title')}» у вас итоговый балл {result.get('score_total')} и категория «{label}»."
        if meaning:
            text += f" {meaning}"
        text += " Это скрининговый результат, а не диагноз."
        return text
    text = f"For the assessment “{result.get('graph_title')}”, your total score is {result.get('score_total')} and the category is “{label}”."
    if meaning:
        text += f" {meaning}"
    text += " This is a screening result, not a diagnosis."
    return text


def _summarize_answers(answers: list[dict[str, Any]], graph: dict[str, Any], language: str) -> list[str]:
    summaries: list[str] = []
    report_rules = [str(rule) for rule in (graph.get("report_rules") or []) if str(rule).strip()]
    answer_map = {str(item.get("question_text") or ""): item for item in answers}

    def answer_for_keywords(*keywords: str) -> str | None:
        for question_text, answer in answer_map.items():
            low = question_text.lower()
            if any(keyword in low for keyword in keywords):
                return str(answer.get("selected_option") or answer.get("raw_answer") or "").strip() or None
        return None

    exhaustion = answer_for_keywords("exhaust", "истощ", "устал")
    detachment = answer_for_keywords("cynical", "detached", "numb", "цинич", "отстран")
    impact = answer_for_keywords("relationships", "clients", "patients", "colleagues", "effectiveness", "concentration", "отношени", "эффектив")

    if any("summarize exhaustion" in rule.lower() or "summary exhaustion" in rule.lower() for rule in report_rules) and exhaustion:
        summaries.append(
            f"Exhaustion: {exhaustion}." if language == "en" else f"Истощение: {exhaustion}."
        )
    if any("summarize detachment" in rule.lower() or "summary detachment" in rule.lower() for rule in report_rules) and detachment:
        summaries.append(
            f"Detachment: {detachment}." if language == "en" else f"Отстраненность: {detachment}."
        )
    if any("summarize work impact" in rule.lower() or "summary work impact" in rule.lower() for rule in report_rules) and impact:
        summaries.append(
            f"Work impact: {impact}." if language == "en" else f"Влияние на работу: {impact}."
        )
    return summaries


def _safe_recommendations(result: dict[str, Any], graph: dict[str, Any], language: str) -> list[str]:
    label = str(((result.get("risk_band") or {}).get("label") or "")).lower()
    topic = str(graph.get("topic") or "").lower()
    recommendations: list[str] = []
    if topic == "stress" and "burnout" in " ".join(str(rule).lower() for rule in graph.get("report_rules", [])):
        if "high" in label:
            recommendations = [
                "Plan a near-term conversation with a clinician or trusted supervisor." if language == "en" else "Запланируйте в ближайшее время разговор с врачом или доверенным руководителем.",
                "Reduce non-essential load and watch for worsening sleep, anxiety, or inability to recover." if language == "en" else "Снизьте необязательную нагрузку и наблюдайте за ухудшением сна, тревоги или отсутствием восстановления.",
            ]
        elif "moderate" in label:
            recommendations = [
                "Review workload and recovery routines over the next 1-2 weeks." if language == "en" else "Пересмотрите нагрузку и режим восстановления на ближайшие 1-2 недели.",
                "If symptoms continue to worsen, seek a clinician's advice." if language == "en" else "Если симптомы продолжают усиливаться, обратитесь за консультацией к врачу.",
            ]
        else:
            recommendations = [
                "Keep tracking recovery, sleep, and work strain." if language == "en" else "Продолжайте отслеживать восстановление, сон и рабочую нагрузку.",
            ]
    elif topic == "diabetes":
        if "very high" in label or "high" in label:
            recommendations = [
                "Consider discussing the result with a clinician and checking formal metabolic labs." if language == "en" else "Рассмотрите обсуждение результата с врачом и выполнение формальных метаболических анализов.",
            ]
        elif "moderate" in label or "elevated" in label:
            recommendations = [
                "Track weight, activity, and nutrition, and consider a planned clinician follow-up." if language == "en" else "Отслеживайте вес, активность и питание и рассмотрите плановый визит к врачу.",
            ]
    if not recommendations:
        recommendations = [
            "Use this result as a screening signal and seek clinical advice if symptoms or concerns continue." if language == "en" else "Используйте этот результат как скрининговый сигнал и обратитесь к врачу, если симптомы или опасения сохраняются."
        ]
    return recommendations


def detailed_report(result: dict[str, Any] | None, language: str) -> str:
    if not isinstance(result, dict):
        return "Нет результата для отчёта." if language == "ru" else "There is no result for a report."
    graph = result.get("_graph") or {}
    answers = result.get("_answers") or []
    payload = build_report_payload(result, graph, answers, language)
    lines = [
        f"{'Подробный отчёт' if language == 'ru' else 'Detailed report'}: {payload.get('title')}",
        f"- {'Итоговый балл' if language == 'ru' else 'Total score'}: {payload.get('score_total')}",
        f"- {'Категория риска' if language == 'ru' else 'Risk category'}: {payload.get('risk_label', '—')}",
    ]
    meaning = payload.get("interpretation")
    if meaning:
        lines.append(f"- {'Интерпретация' if language == 'ru' else 'Interpretation'}: {meaning}")
    if payload.get("summaries"):
        lines.append("")
        lines.append("Персонализированное резюме:" if language == "ru" else "Personalized summary:")
        lines.extend(f"- {item}" for item in payload["summaries"])
    if payload.get("recommendations"):
        lines.append("")
        lines.append("Следующие шаги:" if language == "ru" else "Next steps:")
        lines.extend(f"- {item}" for item in payload["recommendations"])
    lines.append("")
    lines.append("Это скрининговый результат, а не диагноз." if language == "ru" else "This is a screening result, not a diagnosis.")
    return "\n".join(lines)


def _pdf_escape(text: str) -> str:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return "".join(ch if 32 <= ord(ch) <= 126 else "?" for ch in safe)


def _render_report_pdf_fallback(result: dict[str, Any] | None, language: str) -> bytes:
    graph = result.get("_graph") if isinstance(result, dict) else {}
    answers = result.get("_answers") if isinstance(result, dict) else []
    payload = build_report_payload(result, graph or {}, answers or [], language)
    title = str(payload.get("title") or ("Health Assessment Report" if language == "en" else "Otchet"))[:80]
    lines = [
        title,
        "",
        ("Total score" if language == "en" else "Itogovyy ball") + f": {payload.get('score_total')}",
        ("Risk category" if language == "en" else "Kategoriya riska") + f": {payload.get('risk_label') or '—'}",
    ]
    if payload.get("interpretation"):
        lines.append(("Interpretation" if language == "en" else "Interpretatsiya") + f": {payload.get('interpretation')}")
    if payload.get("summaries"):
        lines.append("")
        lines.append("Summary:")
        lines.extend(f"- {item}" for item in payload["summaries"])
    if payload.get("recommendations"):
        lines.append("")
        lines.append("Next steps:" if language == "en" else "Sleduyushchie shagi:")
        lines.extend(f"- {item}" for item in payload["recommendations"])
    lines.append("")
    lines.append("This is a screening result, not a diagnosis." if language == "en" else "Eto skriningovyy rezultat, a ne diagnoz.")
    lines = lines[:45]
    stream_lines = ["BT", "/F1 12 Tf", "50 760 Td", "14 TL"]
    first = True
    for line in lines:
        escaped = _pdf_escape(str(line))
        if first:
            stream_lines.append(f"({escaped}) Tj")
            first = False
        else:
            stream_lines.append(f"T* ({escaped}) Tj")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("ascii", errors="ignore")
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        b"4 0 obj\n<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    return bytes(pdf)


def _render_report_pdf_reportlab(result: dict[str, Any] | None, language: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    graph = result.get("_graph") if isinstance(result, dict) else {}
    answers = result.get("_answers") if isinstance(result, dict) else []
    payload = build_report_payload(result, graph or {}, answers or [], language)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=str(payload.get("title") or "Health Assessment Report"),
    )
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    body_style = styles["BodyText"]
    body_style.leading = 14
    body_style.spaceAfter = 4
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#1f4b7a"),
        spaceBefore=10,
        spaceAfter=6,
    )
    small_style = ParagraphStyle(
        "SmallMuted",
        parent=styles["BodyText"],
        textColor=colors.HexColor("#666666"),
        fontSize=9,
        leading=12,
    )

    score_label = "Total score" if language == "en" else "Суммарный балл"
    category_label = "Risk category" if language == "en" else "Категория риска"
    interpretation_label = "Interpretation" if language == "en" else "Интерпретация"
    summary_label = "Personalized summary" if language == "en" else "Персонализированное резюме"
    recommendations_label = "Next steps" if language == "en" else "Следующие шаги"
    disclaimer = (
        "This report is a screening output and does not establish a formal medical diagnosis."
        if language == "en"
        else "Этот отчёт отражает результат скрининга и не устанавливает формальный медицинский диагноз."
    )

    story: list[Any] = []
    story.append(Paragraph(str(payload.get("title") or ("Health Assessment Report" if language == "en" else "Отчёт по опроснику")), title_style))
    story.append(Spacer(1, 6))

    score_table = Table(
        [
            [score_label, str(payload.get("score_total") or "—")],
            [category_label, str(payload.get("risk_label") or "—")],
        ],
        colWidths=[55 * mm, 110 * mm],
    )
    score_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f7fb")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d3e0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d8e0ea")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(score_table)

    if payload.get("interpretation"):
        story.append(Spacer(1, 8))
        story.append(Paragraph(interpretation_label, section_style))
        story.append(Paragraph(str(payload.get("interpretation")), body_style))

    if payload.get("summaries"):
        story.append(Spacer(1, 8))
        story.append(Paragraph(summary_label, section_style))
        for item in payload["summaries"]:
            story.append(Paragraph(f"• {item}", body_style))

    if payload.get("recommendations"):
        story.append(Spacer(1, 8))
        story.append(Paragraph(recommendations_label, section_style))
        for item in payload["recommendations"]:
            story.append(Paragraph(f"• {item}", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph(disclaimer, small_style))
    doc.build(story)
    return buffer.getvalue()


def render_report_pdf(result: dict[str, Any] | None, language: str) -> bytes:
    try:
        return _render_report_pdf_reportlab(result, language)
    except Exception:
        return _render_report_pdf_fallback(result, language)


def build_report_payload(result: dict[str, Any] | None, graph: dict[str, Any] | None, answers: list[dict[str, Any]] | None, language: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"title": None, "score_total": None, "risk_label": None, "interpretation": None, "summaries": [], "recommendations": []}
    graph = graph or {}
    answers = answers or []
    risk_band = result.get("risk_band") or {}
    return {
        "title": result.get("graph_title"),
        "score_total": result.get("score_total"),
        "risk_label": risk_band.get("label", "—"),
        "interpretation": risk_band.get("meaning"),
        "summaries": _summarize_answers(answers, graph, language),
        "recommendations": _safe_recommendations(result, graph, language),
    }


def render_report_html(result: dict[str, Any] | None, language: str) -> str:
    if not isinstance(result, dict):
        title = "Отчёт недоступен" if language == "ru" else "Report unavailable"
        body = "Для этой сессии пока нет результата." if language == "ru" else "There is no result for this session yet."
        return (
            "<html><head><meta charset='utf-8'><title>"
            + title
            + "</title></head><body><h1>"
            + title
            + "</h1><p>"
            + body
            + "</p></body></html>"
        )

    graph = result.get("_graph") or {}
    answers = result.get("_answers") or []
    payload = build_report_payload(result, graph, answers, language)
    title = str(payload.get("title") or ("Health Assessment Report" if language == "en" else "Отчёт по ассессменту"))
    score_label = "Total score" if language == "en" else "Суммарный балл"
    category_label = "Risk category" if language == "en" else "Категория риска"
    interpretation_label = "Interpretation" if language == "en" else "Интерпретация"
    recommendations_label = "Next steps" if language == "en" else "Следующие шаги"
    summary_label = "Personalized summary" if language == "en" else "Персонализированное резюме"
    disclaimer = (
        "This is a screening result, not a diagnosis or treatment recommendation."
        if language == "en"
        else "Это скрининговый результат, а не диагноз и не рекомендация по лечению."
    )
    meaning = str(payload.get("interpretation") or "")
    summaries_html = "".join(f"<li>{item}</li>" for item in payload.get("summaries", []))
    recommendations_html = "".join(f"<li>{item}</li>" for item in payload.get("recommendations", []))
    return f"""<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 40px; color: #1f2937; }}
    .card {{ max-width: 760px; padding: 28px; border: 1px solid #e5e7eb; border-radius: 16px; background: #ffffff; }}
    h1 {{ margin: 0 0 20px; }}
    .metric {{ margin: 12px 0; font-size: 18px; }}
    .label {{ color: #6b7280; display: block; font-size: 13px; text-transform: uppercase; letter-spacing: .04em; }}
    .value {{ font-weight: 600; font-size: 22px; }}
    h2 {{ margin-top: 28px; font-size: 18px; }}
    ul {{ padding-left: 20px; }}
    .disclaimer {{ margin-top: 28px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #6b7280; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    <div class="metric"><span class="label">{score_label}</span><span class="value">{payload.get("score_total")}</span></div>
    <div class="metric"><span class="label">{category_label}</span><span class="value">{payload.get("risk_label", "—")}</span></div>
    <div class="metric"><span class="label">{interpretation_label}</span><span class="value">{meaning or '—'}</span></div>
    {f"<h2>{summary_label}</h2><ul>{summaries_html}</ul>" if summaries_html else ""}
    <h2>{recommendations_label}</h2>
    <ul>{recommendations_html}</ul>
    <div class="disclaimer">{disclaimer}</div>
  </div>
</body>
</html>"""


def normalize_answer(question: dict[str, Any], raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    low = _normalize_text(text)
    options = question.get("options", [])

    if options:
        if low.isdigit():
            idx = int(low) - 1
            if 0 <= idx < len(options):
                option = options[idx]
                return {
                    "status": "full_match",
                    "raw_answer": raw_text,
                    "selected_option": option.get("label"),
                    "value": option.get("value"),
                    "score": float(option.get("score", 0.0)),
                }

        for option in options:
            label = _normalize_text(str(option.get("label", "")))
            value = _normalize_text(str(option.get("value", "")))
            if low and (low == label or low == value):
                return {
                    "status": "full_match",
                    "raw_answer": raw_text,
                    "selected_option": option.get("label"),
                    "value": option.get("value"),
                    "score": float(option.get("score", 0.0)),
                }

        if low in YES_WORDS:
            for option in options:
                label = _normalize_text(str(option.get("label", "")))
                value = _normalize_text(str(option.get("value", "")))
                if label in YES_WORDS or value in YES_WORDS:
                    return {
                        "status": "full_match",
                        "raw_answer": raw_text,
                        "selected_option": option.get("label"),
                        "value": option.get("value"),
                        "score": float(option.get("score", 0.0)),
                    }
        if low in NO_WORDS:
            for option in options:
                label = _normalize_text(str(option.get("label", "")))
                value = _normalize_text(str(option.get("value", "")))
                if label in NO_WORDS or value in NO_WORDS:
                    return {
                        "status": "full_match",
                        "raw_answer": raw_text,
                        "selected_option": option.get("label"),
                        "value": option.get("value"),
                        "score": float(option.get("score", 0.0)),
                    }

    number_match = re.search(r"(\d+(?:[.,]\d+)?)", low)
    if number_match:
        value = float(number_match.group(1).replace(",", "."))
        return {
            "status": "full_match",
            "raw_answer": raw_text,
            "selected_option": None,
            "value": value,
            "score": 0.0,
        }

    return {"status": "no_match", "raw_answer": raw_text}


def find_risk_band(graph: dict[str, Any], score_total: float) -> dict[str, Any] | None:
    for band in graph.get("risk_bands", []):
        try:
            if float(band["min_score"]) <= score_total <= float(band["max_score"]):
                return band
        except Exception:
            continue
    return None


def evaluate_rule_nodes(graph: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any] | None:
    answer_map: dict[str, Any] = {}
    for answer in answers:
        qtext = str(answer.get("question_text") or "").strip().lower()
        if qtext:
            answer_map[qtext] = answer.get("value")
    matched: list[dict[str, Any]] = []
    for node in graph.get("rule_nodes", []) or []:
        conditions = node.get("conditions_ast") or []
        if not conditions:
            continue
        ok = True
        for clause in conditions:
            field = str(clause.get("field") or "").strip().lower()
            op = str(clause.get("operator") or "").strip()
            expected = str(clause.get("value") or "").strip()
            actual = answer_map.get(field)
            if actual is None:
                ok = False
                break
            if op in {">=", "<=", ">", "<", "="}:
                try:
                    actual_num = float(actual)
                    expected_num = float(expected.replace(",", "."))
                except Exception:
                    ok = False
                    break
                if op == ">=" and not (actual_num >= expected_num):
                    ok = False
                elif op == "<=" and not (actual_num <= expected_num):
                    ok = False
                elif op == ">" and not (actual_num > expected_num):
                    ok = False
                elif op == "<" and not (actual_num < expected_num):
                    ok = False
                elif op == "=" and not (actual_num == expected_num):
                    ok = False
            elif op == "contains":
                if expected.lower() not in str(actual).lower():
                    ok = False
            elif op == "present":
                ok = actual not in {None, ""}
            if not ok:
                break
        if ok:
            matched.append(node)
    if not matched:
        return None
    top = matched[0]
    return {
        "label": top.get("label", "Rule matched"),
        "meaning": top.get("outcome"),
        "matched_rules": [node.get("id") for node in matched],
    }


def apply_answer(graph: dict[str, Any], assessment_state: dict[str, Any], normalized: dict[str, Any]) -> dict[str, Any]:
    language = assessment_state.get("language", "ru")
    if normalized.get("status") != "full_match":
        return {
            "assessment_state": assessment_state,
            "completed": False,
            "reply_text": (
                "Я не смог понять ответ. Попробуйте ответить ещё раз."
                if language == "ru"
                else "I could not understand the answer. Please try again."
            ) + "\n\n" + render_question(graph, assessment_state),
        }

    current_question = get_current_question(graph, assessment_state)
    assessment_state["answers"].append(
        {
            "question_id": current_question.get("id") if current_question else None,
            "question_text": current_question.get("text") if current_question else None,
            "raw_answer": normalized.get("raw_answer"),
            "value": normalized.get("value"),
            "selected_option": normalized.get("selected_option"),
            "score": normalized.get("score", 0.0),
        }
    )
    assessment_state["score_total"] = float(assessment_state.get("score_total", 0.0)) + float(normalized.get("score", 0.0))
    selected_option = None
    current_question_options = current_question.get("options", []) if current_question else []
    normalized_value = normalized.get("value")
    for option in current_question_options:
        if option.get("value") == normalized_value:
            selected_option = option
            break
    next_question_id = selected_option.get("next_question_id") if isinstance(selected_option, dict) else None
    next_index = _question_index_by_id(graph, next_question_id)
    if next_index is not None:
        assessment_state["question_index"] = next_index
    else:
        assessment_state["question_index"] = int(assessment_state.get("question_index", 0)) + 1

    next_question = get_current_question(graph, assessment_state)
    if next_question is not None:
        return {
            "assessment_state": assessment_state,
            "completed": False,
            "reply_text": render_question(graph, assessment_state),
        }

    if graph.get("artifact_type") == "clinical_rule_graph":
        risk_band = evaluate_rule_nodes(graph, assessment_state["answers"]) or {"label": "No rule matched", "meaning": "No explicit diagnostic rule was matched."}
        result = {
            "graph_title": graph.get("title"),
            "score_total": assessment_state.get("score_total", 0.0),
            "risk_band": risk_band,
        }
        assessment_state["status"] = "completed"
        assessment_state["result"] = result
        label = risk_band.get("label", "—")
        meaning = risk_band.get("meaning")
        reply = (
            f"Спасибо, rule-based скрининг завершён.\n\nТема: {graph.get('title')}\nКатегория результата: {label}\nИнтерпретация: {meaning or '—'}\n\nЭто скрининговый результат, а не диагноз."
            if language == "ru"
            else f"Thank you, the rule-based assessment is complete.\n\nTopic: {graph.get('title')}\nResult category: {label}\nInterpretation: {meaning or '—'}\n\nThis is a screening/triage result, not a diagnosis."
        )
        return {"assessment_state": assessment_state, "completed": True, "reply_text": reply}

    result = {
        "graph_title": graph.get("title"),
        "score_total": assessment_state.get("score_total", 0.0),
        "risk_band": find_risk_band(graph, float(assessment_state.get("score_total", 0.0))),
        "_graph": graph,
        "_answers": list(assessment_state["answers"]),
    }
    assessment_state["status"] = "completed"
    assessment_state["result"] = result

    band = result.get("risk_band") or {}
    label = band.get("label", "—")
    recommendations = _safe_recommendations(result, graph, language)
    reply = (
        f"Спасибо, опрос завершён.\n\nТема: {graph.get('title')}\nСуммарный балл: {result['score_total']}\nКатегория результата: {label}\n\nСледующий шаг: {recommendations[0]}\n\nЕсли хотите, я могу объяснить результат или дать подробный отчёт."
        if language == "ru"
        else f"Thank you, the assessment is complete.\n\nTopic: {graph.get('title')}\nTotal score: {result['score_total']}\nResult category: {label}\n\nSuggested next step: {recommendations[0]}\n\nIf you want, I can explain the result or provide a detailed report."
    )
    return {"assessment_state": assessment_state, "completed": True, "reply_text": reply}
