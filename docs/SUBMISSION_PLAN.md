# Submission Plan

This file maps the current MVP against the assignment and organizes remaining work into three priority tiers.

## Must-Have

These items are required for a strong submission.

### 1. Prompt-driven scenario definition

The system must clearly show that an assessment scenario can be changed without code edits.

Target:

- one specialist can define the scenario via a single prompt
- the system compiles it into a runnable graph

### 2. Specialist copilot mode

This is an intentional product-strengthener for the assignment.

Target:

- the specialist does not need a perfect prompt upfront
- the bot can help them build that prompt in chat

Why it matters:

- it solves a harder problem than simple prompt execution

### 3. One polished end-to-end assessment

Target:

- specialist creates scenario
- graph is compiled and published
- patient completes it
- patient receives result and report

Canonical demo:

- `Diabetes / FINDRISC-like assessment`

### 4. Adaptive logic

Target:

- at least one demo scenario must branch based on answers

Canonical demo:

- `Burnout branching assessment`

### 5. Structured report output

Target:

- patient receives a usable report
- text report is required
- HTML/web report is a strong enhancement

## Should-Have

These items make the submission clearly stronger.

### 1. Human-readable patient explanations

Avoid internal debug wording in user-facing replies.

### 2. Language-agnostic search and runtime

The same graph should be discoverable from English and Russian inputs.

### 3. Canonical prompt examples

The repo should include:

- one diabetes prompt
- one burnout prompt

### 4. Two specialist authoring paths in docs

Both must be described explicitly:

- `single prompt mode`
- `assistant mode`

### 5. Clean demo script

There should be a short sequence for:

- specialist demo
- patient demo

## Nice-to-Have

These are valuable, but secondary to the happy path.

### 1. HTML report endpoint

This is a lightweight web-format deliverable for the assignment.

### 2. Guardrails integration plan

Current status:

- not part of the runtime stack yet

Value:

- shows clear future validation strategy

### 3. Additional UX polish

Examples:

- better visual report
- clearer branching explanation
- more polished specialist onboarding

## Current Status Snapshot

Implemented or materially addressed:

- typed prompt-driven authoring pipeline
- specialist copilot mode
- patient runtime
- multilingual matching improvements
- adaptive questionnaire branching support
- HTML report endpoint
- diabetes and burnout demo scenarios in docs
