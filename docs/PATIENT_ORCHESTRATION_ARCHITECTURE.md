# PATIENT_ORCHESTRATION_ARCHITECTURE.md

## 1. Purpose

The patient-side assistant must behave like a conversational orchestrator over a graph library.

It must support the following loop:

1. user starts free conversation
2. system analyzes the dialogue
3. system searches the graph library
4. system proposes a suitable assessment
5. user gives consent
6. system executes the selected graph
7. system presents the result
8. system returns to free conversation

---

## 2. Why this is necessary

A bot that starts from one preselected graph is too rigid.

The target assistant must instead:
- listen first
- discover the right graph
- ask permission
- run the graph
- return to dialogue after completion

---

## 3. Main architectural components

- User Bot
- Patient Orchestrator / Patient Controller
- Conversation Analyzer
- Graph Registry
- Graph Search
- Assessment Selector
- Consent Manager
- Graph Runtime
- Result Interpreter
- Session Store
- Response Renderer

---

## 4. Main modes

- free_conversation
- awaiting_consent
- assessment_in_progress
- paused_assessment
- post_assessment

---

## 5. Main idea

The patient assistant is not “a questionnaire bot”.

It is a **conversation-first assistant that may enter and exit assessment runtime when relevant**.

