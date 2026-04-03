# SPECIALIST_ARCHITECTURE.md

## 1. Purpose

The specialist side exists to create, refine, compile, and publish assessment graphs.

It is an **authoring workflow**, not a user questionnaire flow.

---

## 2. Specialist-side principle

The specialist bot is a **controller-based copilot** operating on a mutable draft.

It should not behave like:
- a rigid form
- a blind slot-filler
- a compile-only wizard

It should behave like:
- a working assistant
- a graph-authoring copilot
- a structured editor over a draft object

---

## 3. Main specialist-side objects

### Draft
Contains the emerging assessment structure.

### Compiled graph
Executable artifact created from the draft.

### Published graph
Graph that has been handed off to the graph library and patient-side runtime.

---

## 4. Workflow stages

### 4.1 Source intake
The specialist can provide:
- guideline fragments
- article text
- scale definitions
- scoring tables
- noisy webpage dumps
- free-form authoring text

### 4.2 Draft update
Definition agent extracts structure and merges it into the draft.

### 4.3 Draft inspection
The specialist may ask:
- what did you understand
- show questions
- show scoring
- show risk bands
- show report rules
- show safety rules

### 4.4 Draft edit
The specialist may provide natural-language change requests.

### 4.5 Compile
Compiler turns the draft into a runtime-ready graph with a unique graph id.

### 4.6 Publish
Published graph becomes:
- available as active graph
- searchable via graph registry

---

## 5. Why the specialist side needs a controller

Without the controller, the specialist bot becomes:
- too scripted
- too clarification-heavy
- too rigid
- compile-oriented instead of authoring-oriented

The controller solves this by:
- interpreting specialist intent
- deciding the correct operation
- preserving a natural working dialogue

