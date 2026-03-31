# specialist-controller.md

## 1. Purpose

The Specialist Controller is the core reasoning loop of the specialist bot.

It replaces the old scripted specialist interaction model.

The controller does not behave like a simple intent classifier plus fixed templates.  
Instead, it acts as a bounded copilot that:
- understands the latest specialist message in context
- inspects the current draft state
- decides what operation should happen next
- produces a natural reply after that operation

---

## 2. Why this exists

The original problem with the specialist flow was not only extraction quality.

The deeper issue was that the bot:
- behaved like a rigid scripted algorithm
- repeated compile-oriented responses
- did not understand what the specialist wanted to do with the draft
- did not feel like a working assistant

The controller layer solves this by centering the conversation around:
- context
- the current draft object
- allowed actions

---

## 3. Allowed action space

The controller operates only within these workflow actions:

- `DIRECT_REPLY`
- `SHOW_PREVIEW`
- `SHOW_QUESTIONS`
- `SHOW_SCORING`
- `SHOW_RISK_BANDS`
- `SHOW_REPORT_RULES`
- `SHOW_SAFETY_RULES`
- `UPDATE_DRAFT_FROM_INPUT`
- `APPLY_EDIT_INSTRUCTION`
- `ASK_CLARIFICATION`
- `EXPLAIN_NEXT_STEP`
- `COMPILE_DRAFT`
- `PUBLISH_GRAPH`
- `RESTART_WORKFLOW`

This restriction is important: it lets the controller “think” while still staying inside graph-building boundaries.

---

## 4. Inputs to controller reasoning

For each turn, the controller sees:
- latest user message
- current user language
- current draft summary
- current focus
- compiled graph id, if available
- recent conversation history

This gives it enough context to answer naturally and choose the correct workflow action.

---

## 5. Typical controller decisions

### Example 1 — preview request
User:
- “что ты понял?”
- “покажи что получилось”

Expected action:
- `SHOW_PREVIEW`

### Example 2 — inspect questions
User:
- “покажи вопросы”

Expected action:
- `SHOW_QUESTIONS`

### Example 3 — edit request
User:
- “измени вопрос 3”
- “давай поправим scoring”

Expected action:
- `APPLY_EDIT_INSTRUCTION`

### Example 4 — new source material
User pastes:
- article
- guideline fragment
- questionnaire scale
- noisy webpage text

Expected action:
- `UPDATE_DRAFT_FROM_INPUT`

### Example 5 — publish
User:
- “опубликуй граф”
- “publish”

Expected action:
- `PUBLISH_GRAPH`

---

## 6. Fallback behavior

The specialist controller must not crash the whole specialist flow if the provider or reasoning call fails.

Fallback behavior:
- use cheap deterministic action inference from the latest message
- continue the workflow
- preserve usability

This is essential for real MVP robustness.

---

## 7. Final response generation

The final user-visible reply is also generated through the controller model.

However:
- it sees the action that was executed
- it sees the tool result
- it sees the updated draft summary

Therefore it can respond naturally without behaving like a rigid scripted state machine.

---

## 8. Boundaries

The controller must remain inside the role of a graph-building copilot.

It must not:
- diagnose illness
- create treatment plans
- recommend medication
- drift into unrestricted medical chat

This is enforced through:
- policy
- system prompts
- action space restriction
