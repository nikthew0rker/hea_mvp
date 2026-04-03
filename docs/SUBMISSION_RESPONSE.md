# Submission Response

## What I Built

I built an MVP of a `prompt-driven health assessment engine` with two connected agent surfaces:

- a `Specialist Bot` for authoring assessment scenarios
- a `User Bot` for running those assessments with end users

Telegram bot handles:

- `@hea_specialist_mvp_bot`
- `@hea_user_mvp_bot`

The key idea is that the assessment scenario can be changed without code edits.

The specialist side supports two authoring modes:

1. `Single prompt mode`
- a specialist can send one large scenario-defining prompt
- the system compiles it into a runnable assessment graph

2. `Assistant mode`
- the specialist does not need a perfect prompt upfront
- the bot helps refine the topic, questions, branching, scoring, risk bands, and report structure in chat

This means the system does not only execute a scenario prompt. It can also help create that prompt collaboratively.

The MVP currently supports:

- `questionnaire`
- `anamnesis_flow`
- `clinical_rule_graph`

For the assignment demo, I prepared two scenarios:

- `Diabetes / FINDRISC-like questionnaire` as a simple scored flow
- `Burnout questionnaire` as a more adaptive branching flow

The patient side can:

- identify a relevant published assessment
- ask for consent
- run the assessment
- calculate the result
- return a structured report with personalized summary and safe next steps
- provide the report as text, HTML, and PDF
- send the PDF directly into Telegram chat as a file when the user asks for `pdf` / `пдф`

There are report endpoints on the patient controller:

- `GET /report/{conversation_id}`
- `GET /report/{conversation_id}.pdf`

## Key Technical Decisions

I intentionally avoided building this as a single prompt-only chatbot.

Instead, I used a typed workflow:

`specialist message -> intent analysis -> typed spec -> validation/review -> apply -> compile -> publish -> patient runtime`

Main design choices:

- `LangGraph` for orchestration and stateful workflows
- `Pydantic` for typed intermediate representation and validation
- `FastAPI` for controller boundaries
- `SQLite` for graph registry, sessions, drafts, and audit trail
- `Together AI` for model inference with role separation

I split model responsibilities by role instead of using one universal model:

- controller / analyst
- compiler
- critic
- fast reply

That made the system more controllable and reduced the fragility of pure prompt-only logic.

I also separated:

- draft state
- compiled graph state
- published graph state

This matters because only published graphs are available to end users.

## Why I Chose This Approach

The assignment asks for a `prompt-driven` engine where specialists can define:

- questions
- adaptive branching
- scoring
- clinical guidance
- report structure

I wanted to preserve that flexibility while still making the system reliable enough to debug and extend.

So instead of treating the scenario as unstructured chat forever, I compile it into a typed internal representation and then execute it from there.

This gives a better balance between:

- flexibility for specialists
- safety and control in the runtime
- clarity in debugging and iteration

I also think the `assistant mode` makes the solution stronger than a simple prompt runner, because in real usage many specialists will not arrive with a perfect prompt already written.

## What Is Already Working

- specialist can create or refine an assessment in chat
- specialist can apply, compile, and publish a graph
- patient can discover a published graph and complete it
- multilingual matching was improved so search does not depend only on one language
- branching logic is supported in questionnaire runtime through answer-driven next-question transitions
- text reports, HTML reports, and PDF export are available

## What I Would Do Next

If I continued beyond this MVP, I would prioritize:

1. richer branching DSL for more complex adaptive flows
2. stronger domain validators
3. PDF export in addition to HTML report
4. better semantic retrieval for graph selection
5. stronger UI layer for specialist review and selective approval
6. optional Guardrails integration as a post-generation validation / re-ask layer

## Example Scenario Prompt

The repository includes prompt examples for both demo scenarios:

- [`SCENARIOS.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/SCENARIOS.md)

In particular:

- a `Diabetes / FINDRISC-like` prompt for a simple scored questionnaire
- a `Burnout` prompt for an adaptive branching questionnaire

## Repository Notes

Supporting documents:

- [`README.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/README.md)
- [`ARCHITECTURE.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/ARCHITECTURE.md)
- [`MODEL_ROLES.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/MODEL_ROLES.md)
- [`SCENARIOS.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/SCENARIOS.md)
- [`SUBMISSION_PLAN.md`](/Users/nik/PycharmProjects/PythonProject/hea_mvp/docs/SUBMISSION_PLAN.md)
