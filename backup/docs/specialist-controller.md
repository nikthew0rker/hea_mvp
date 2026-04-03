# specialist-controller.md

## 1. Purpose

Specialist Controller is the specialist-side reasoning loop.

It decides:
- what the specialist wants to do
- which workflow action should happen next
- how to explain the result naturally

---

## 2. Input context

The controller sees:
- latest specialist message
- current draft summary
- current focus
- compile status
- recent chat history
- specialist language

---

## 3. Allowed actions

Typical actions:
- SHOW_PREVIEW
- SHOW_QUESTIONS
- SHOW_SCORING
- SHOW_RISK_BANDS
- UPDATE_DRAFT_FROM_INPUT
- APPLY_EDIT_INSTRUCTION
- COMPILE_DRAFT
- PUBLISH_GRAPH
- ASK_CLARIFICATION
- EXPLAIN_NEXT_STEP

---

## 4. Why it matters

This makes the specialist bot feel like a copilot rather than a rigid authoring form.

---

## 5. Boundary

The controller must stay within graph authoring and workflow support.  
It must not turn into unrestricted medical consultation.

