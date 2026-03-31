# patient-orchestrator.md

## 1. Purpose

Patient Orchestrator is the main patient-side decision-making layer.

It coordinates:
- free conversation
- graph discovery
- graph offer
- consent
- graph runtime
- result presentation
- return to free conversation

---

## 2. Main responsibilities

- decide which mode the conversation is in
- analyze whether the user is asking for help, describing a problem, or answering a question
- search for relevant graph candidates
- select or propose a graph
- collect consent
- hand off to graph runtime
- preserve session state

---

## 3. Why it is needed

Without the orchestrator:
- the bot becomes hardwired to one graph
- greetings and free conversation feel broken
- graph selection never happens
- runtime starts too early
- the assistant cannot re-enter free conversation after result

---

## 4. Session model

The orchestrator should maintain:
- mode
- language
- discovered graphs
- selected graph
- consent status
- assessment state
- last result

