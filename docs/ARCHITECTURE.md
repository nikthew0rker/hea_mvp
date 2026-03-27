# ARCHITECTURE.md

# Prompt-Driven Health Assessment Engine

## 1. Overview

This project implements a prompt-driven health assessment engine for short health-risk microproducts.

The core requirement is simple:

- a specialist can change assessment behavior without changing code
- a user can complete an adaptive assessment flow
- the system produces a personalized report

The architecture is intentionally lightweight. It is designed to solve the MVP assignment directly, while keeping the right boundaries for future product growth.

The central architectural idea is:

**specialist-defined input → compile into canonical assessment graph → runtime execution → personalized report**


---

## 2. MVP Scope

### Included in MVP

- text-based assessment definition
- compile step from assessment definition into executable graph
- adaptive runtime flow for end users
- deterministic branching and score calculation
- final report generation in web format
- optional PDF export
- one main demo assessment
- one additional assessment definition to demonstrate extensibility
- lightweight validation, safety rules, and evaluation cases

### Planned next iteration (TODO)

- specialist-facing authoring UI
- graph visual editor
- visual review/edit workflow before publishing
- richer evidence integrations
- assessment simulation mode for specialists
- analytics dashboard

The MVP intentionally focuses on the minimum end-to-end slice required by the assignment.

---

## 3. Architectural Principles

### 3.1 Spec-driven

Assessment behavior is defined outside of code.

A specialist provides:

- questions
- answer types
- branching rules
- scoring rules
- risk bands
- report structure
- safety requirements

The application code remains generic and reusable.

### 3.2 Compiler + Runtime split

The system separates assessment definition from assessment execution.

- **Compiler phase** transforms specialist input into a validated executable graph
- **Runtime phase** executes only approved compiled graph versions

This makes execution predictable and easier to test.

### 3.3 Graph runtime

The assessment is executed as a directed graph of states.

This allows:

- adaptive branching
- explicit transitions
- deterministic score updates
- transparent session state

### 3.4 Guardrails-first

Safety is built into the architecture rather than added as an afterthought.

The system constrains:

- invalid or incomplete specs
- unsafe wording in reports
- diagnosis-like outputs
- treatment recommendations
- red-flag situations

### 3.5 Eval-driven

The MVP includes a small deterministic evaluation layer.

This ensures that:

- branching is reproducible
- scoring is reproducible
- required report sections are present
- invalid specs are rejected
- red-flag behavior is handled consistently

### 3.6 Regulated conversational freedom

The runtime graph controls information goals and decision boundaries, not exact phrasing.

This means the system does not treat every graph node as a fixed scripted chatbot message.  
Instead, each node defines what must be collected or confirmed, while the conversational layer is allowed to vary phrasing within controlled limits.

This approach reduces the feeling of a rigid questionnaire while preserving deterministic branching, scoring, and safety behavior.

---

## 4. High-Level Architecture

~~~text
[ Specialist-defined assessment input ]
                |
                v
        [ Definition Layer ]
                |
                v
     [ Compiler + Validation ]
                |
                v
 [ Canonical Compiled Assessment Graph ]
                |
                v
          [ Runtime Layer ]
                |
                v
        [ Web / Chat UI Flow ]
                |
                v
         [ Final User Report ]
~~~

The system is intentionally decomposed into three lightweight layers:

- **Definition Layer**
- **Runtime Layer**
- **Infrastructure Layer**

This keeps the design modular enough to evolve into a product, while staying small enough for MVP delivery within a few days.

---

## 5. Canonical Artifact

The canonical artifact of the system is the **compiled assessment graph**.

Specialist-defined input is the authoring source, but it is not executed directly.  
The compiler transforms that input into a compiled graph, which becomes the approved executable representation used for:

- validation
- runtime execution
- scoring
- reporting
- versioning

This allows the architecture to remain prompt/spec-driven while keeping runtime behavior stable and controlled.

---

## 6. Main Layers

## 6.1 Definition Layer

The Definition Layer is responsible for turning specialist-authored input into a runtime-ready assessment graph.

Responsibilities:

- accept text-based assessment definition
- normalize questions, rules, and report structure
- optionally enrich with evidence/guideline references
- build graph nodes and transitions
- validate graph integrity
- attach safety metadata
- produce a compiled graph artifact

### Definition input format

For MVP, the source input is text-first.  
This can be YAML, Markdown, or another structured text format.

Example contents:

- assessment metadata
- questions
- branching rules
- scoring rules
- risk bands
- report sections
- disclaimer/safety instructions

### TODO: specialist authoring UX

The architecture includes a natural path toward a specialist-facing authoring interface, but this is **not required for MVP delivery**.

Planned next iteration:

- specialist-facing authoring UI
- graph visual editor
- visual review/edit loop

---

## 6.2 Runtime Layer

The Runtime Layer executes the compiled graph.

Responsibilities:

- load a published compiled graph
- create a session
- show the next question
- validate the answer
- update score and flags
- follow the graph transitions
- finish the assessment
- generate a final report

In addition to graph execution, the Runtime Layer includes a lightweight conversational orchestration component.

Its role is to make the interaction less scripted while keeping the graph logic intact.  
The graph determines what information must be collected.  
The conversational layer determines how to ask for it in a more natural way.

The runtime never executes raw specialist text directly.  
It only executes the compiled graph artifact.

### 6.2.1 Conversation Orchestrator

The Runtime Layer includes a lightweight **Conversation Orchestrator**.

This component does not replace the graph engine.  
Instead, it sits on top of it and improves the conversational experience.

Responsibilities:

- interpret free-text user responses
- extract one or more structured values from a single answer
- decide whether a node is already satisfied
- confirm inferred values instead of re-asking
- merge nearby information requests when appropriate
- return the flow back to the graph safely

This allows the system to remain graph-driven without becoming an overly rigid scripted questionnaire.

---

## 6.3 Infrastructure Layer

The Infrastructure Layer provides supporting capabilities:

- storage
- API delivery
- LLM access
- report rendering
- optional evidence adapters
- lightweight logging and evaluation

This layer is intentionally simple in MVP.

---

## 7. Compiler Phase

The compiler converts specialist-defined input into an executable graph.

Responsibilities:

- parse the definition input
- normalize structure
- build graph nodes and edges
- validate transitions
- validate score rules
- validate required report sections
- attach safety metadata
- emit an immutable compiled graph version

Compiler output:

- `CompiledAssessmentGraph`

The compiler exists to make the runtime deterministic and safe.

---

## 8. Runtime Phase

The runtime executes a single compiled graph version.

Responsibilities:

- load graph version
- initialize `SessionState`
- traverse graph nodes based on user answers
- calculate score
- assign risk band
- build final structured result
- render final report

The runtime is intentionally assessment-agnostic.  
It can execute multiple assessment types as long as they are compiled into the same graph contract.

---

## 9. Graph Runtime Model

The assessment flow is represented as a directed graph.

Example:

~~~text
Start
  -> q1
  -> q2 or q3
  -> q4
  -> Finish
  -> Report
~~~

Possible node types in MVP:

- `question`
- `finish`
- optional `warning`

Transitions are explicit and deterministic.

Runtime tracks:

- current node
- visited path
- answers
- accumulated score
- flags
- status
- graph version

This graph model is the core reusable engine abstraction.

Importantly, graph nodes represent **information goals**, not necessarily fixed chatbot utterances.

For example, a node may represent the goal "collect average sleep duration" rather than a single hardcoded question.  
This allows the conversational layer to ask directly, infer from free-text, or confirm already-mentioned information depending on confidence and context.

As a result, the graph remains strict at the logic level, while the conversation remains more natural at the language level.

### 9.1 Freedom policy per node

Each graph node can define a **freedom policy** that controls how much conversational flexibility is allowed.

Suggested levels:

- **strict** — minimal freedom; used for safety-critical, consent, or precise quantitative questions
- **guided** — controlled rephrasing and limited merging; used for most standard assessment nodes
- **flexible** — freer conversational style for low-risk context gathering and friction reduction

The freedom policy does not affect the underlying branching or scoring logic.  
It only affects how the system interacts while collecting the required information.

---

## 10. Core Domain Models

### 10.1 DefinitionInput

Specialist-authored assessment definition.

Contains:

- metadata
- questions
- branching rules
- scoring rules
- risk bands
- report format
- safety requirements
- optional references

### 10.2 CompiledAssessmentGraph

Canonical executable assessment artifact.

Contains:

- graph version id
- node definitions
- transitions
- scoring rules
- risk bands
- report schema
- guardrail policy

### 10.3 SessionState

Represents one user execution session.

Contains:

- session id
- graph version id
- current node
- answers
- visited path
- score
- flags
- status

### 10.4 FinalReport

Represents the final structured output.

Contains:

- score
- risk level
- summary
- main contributing factors
- recommendations
- disclaimer
- safety notice when required

### 10.5 ConversationPolicy / NodeInteractionPolicy

Optional conversational metadata can be attached to graph nodes.

Example fields:

- information goal
- required slots
- accepted input modes
- clarification threshold
- confirmation allowed
- merge-with-neighbor allowed
- freedom level

This metadata allows the same graph to remain logically deterministic while making the user interaction more adaptive and less repetitive.

### 10.6 Example of a graph node with conversational freedom policy

Below is an illustrative example of how a compiled graph node can define both deterministic runtime logic and controlled conversational flexibility.

```yaml
node_id: sleep_duration
type: question
goal: collect average sleep duration
required_slots:
  - sleep_duration_hours

accepted_input_modes:
  - direct_answer
  - free_text
  - inferred_from_context

question_examples:
  - "Сколько часов вы обычно спите за ночь?"
  - "Если примерно, сколько часов сна у вас выходит в среднем?"
  - "В двух словах: сколько сна обычно набирается за ночь?"

clarification_policy:
  ask_if_missing: true
  ask_if_confidence_below: 0.8
  max_clarification_turns: 1

confirmation_policy:
  confirmation_allowed: true
  confirm_if_inferred: true
  confirm_if_multiple_slots_extracted: true

merge_policy:
  allow_merge_with:
    - night_awakenings
    - daytime_sleepiness
  prefer_batch_question: true

freedom_policy:
  level: guided
  allow_rephrase: true
  allow_contextual_intro: true
  allow_acknowledgement: true
  allow_multi_slot_capture: true
  must_not_skip_required_slot: true

scoring_rules:
  - if: "sleep_duration_hours < 5"
    add: 3
  - if: "sleep_duration_hours >= 5 and sleep_duration_hours < 6"
    add: 2

transitions:
  - if: "slot_filled('sleep_duration_hours')"
    goto: night_awakenings

guardrails:
  require_numeric_or_range_value: true
  no_clinical_interpretation_in_question: true
```


---

## 11. Safety and Guardrails

Safety is enforced by design.

### Compile-time guardrails

The compiler checks:

- unreachable nodes
- missing transitions
- unsupported question types
- inconsistent score rules
- missing disclaimer requirement
- invalid report schema

### Runtime/report guardrails

The runtime/report layer enforces:

- no diagnosis
- no treatment plan
- no medication recommendation
- explicit disclaimer
- urgent escalation wording for red flags
- lower-confidence wording when answers are incomplete

### Governance boundary

The system does not autonomously invent clinical logic.  
The engine executes specialist-defined logic and uses the model primarily for controlled transformation and report phrasing.

This keeps the product within a risk-awareness / wellness-oriented scope rather than turning it into clinical decision support.

Guardrails also limit conversational freedom.

Even when the interaction style is flexible, the system is not allowed to:
- skip required safety checks
- bypass mandatory graph transitions
- invent missing clinical logic
- turn inferred information into stronger claims without confirmation when confidence is low

---

## 12. Evaluation Strategy

The MVP includes a small deterministic eval suite.

### Required evaluation cases

1. valid definition compiles successfully
2. invalid definition is rejected
3. known answers produce expected branch path
4. known answers produce expected score
5. report contains required sections
6. red-flag response triggers safety notice
7. graph version is stored in session/report artifacts
8. a single free-text answer can satisfy multiple graph nodes when extraction confidence is sufficient
9. already-known information is confirmed instead of re-asked
10. conversational freedom never bypasses mandatory safety or scoring logic

This evaluation layer is intentionally small, but it makes the engine testable and regression-resistant.

---

## 13. Lightweight Observability

The MVP uses lightweight observability rather than heavy platform telemetry.

The system logs:

- compile success/failure
- validation errors
- compiled graph version
- runtime visited path
- score changes
- final risk band
- final report generation


---

## 14. Technology Choices

### Required MVP stack

- **FastAPI** for backend API
- **Pydantic** for contracts and validation
- **SQLite** for MVP persistence
- **direct LLM provider SDK** for controlled model usage
- **HTML report rendering**
- **optional PDF export**

### Optional implementation helpers

#### LangGraph (optional)
Can be used if explicit workflow orchestration is implemented for compile/validation flow.

It is helpful if the implementation benefits from:

- explicit state transitions
- reusable compiler pipeline steps
- conditional flow logic

The MVP does not depend on LangGraph conceptually.

#### LangChain (optional)
Can be used only where it reduces implementation complexity for:

- structured extraction
- tool wrapping
- controlled transformation steps

The architecture does not require LangChain conceptually.

#### React Flow (optional, TODO)
Planned as a future enhancement for graph visualization/editing in specialist-facing tooling.

Not required for core MVP delivery.

---

## 15. Scalability Boundaries

The MVP is intentionally implemented as a lightweight single-service architecture, but it preserves important scalability boundaries.

### 15.1 Versioned compiled graphs

Each compiled graph is versioned and immutable after publication.

### 15.2 Session isolation

Each runtime session is pinned to the graph version it started with.

This avoids execution drift when new versions are introduced.

### 15.3 Assessment catalog growth

The runtime engine is generic and can execute multiple assessment types.

This makes it possible to evolve from one assessment into a small assessment catalog without redesigning the core engine.


---

## 16. Product Fit

The MVP is intentionally shaped around the product context described in the assignment:

- short completion time: 5–10 minutes
- limited number of questions
- clear progress through the flow
- readable and non-technical final report
- actionable but safe recommendations
- final disclaimer / CTA block

The architecture supports these constraints rather than treating them as UI details.

### 16.1 Reducing scripted-chat fatigue

One practical risk of graph-driven assessments is that the interaction can feel too scripted and repetitive.

To reduce this, the MVP runtime is designed so that:

- nodes represent information goals rather than exact fixed messages
- one user response may satisfy multiple data requirements
- previously inferred facts can be confirmed instead of re-asked
- nearby questions may be merged when this does not harm clarity or safety
- the degree of conversational freedom is configurable per node

This keeps the assessment structured without making it feel like a rigid form disguised as a chat.

---

## 17. Alignment with the Hea Assignment

This architecture is centered on the exact MVP requested in the assignment:

- the assessment behavior can be changed without code changes
- the user goes through an adaptive scenario
- answers influence branching and score
- the system generates a personalized report

At the same time, the chosen boundaries — specialist-defined input, compiled canonical graph, reusable runtime engine — create a natural path toward a lightweight product platform for multiple assessments.

This product extensibility is a consequence of good boundaries, not additional MVP scope.

---

## 18. Demo Scenario

The demo should be short and obvious.

### Step 1 — Show the assessment definition
Open a text-based assessment definition, for example:

- `sleep_risk_assessment.yaml`

Show that it defines:

- questions
- branching
- scoring
- report sections

### Step 2 — Run the assessment
Start the runtime flow as a user.

Example questions:

- sleep duration
- night awakenings
- daytime sleepiness
- stress before sleep

### Step 3 — Show the result
Display:

- score
- risk level
- main contributing factors
- recommendations
- disclaimer

### Step 4 — Demonstrate configurability
Swap in a second definition, for example:

- `stress_risk_assessment.yaml`

In the demo, the conversational layer should also show that the system is not limited to one-question-per-turn behavior.

For example, if the user gives a richer answer such as:
"I usually sleep around 5–6 hours, wake up often during the night, and feel sleepy during the day,"

the runtime may extract multiple values, confirm them briefly, and continue to the next missing information goal instead of asking the same points one by one.

Show that:

- code stays the same
- runtime engine stays the same
- behavior and report change because the compiled graph changed

This demo proves the main assignment requirement clearly and quickly.



---

## 19. Delivery Feasibility

The MVP is intentionally constrained to a small number of core components and a single end-to-end flow.

This makes it realistic to implement within a few days with AI-assisted development.


---

## 20. Trade-offs

### Chosen trade-offs

- text-first definition instead of visual authoring in MVP
- compiled graph as canonical artifact instead of raw prompt execution
- lightweight single-service architecture instead of distributed platform
- small evaluation layer instead of heavy QA infrastructure
- simple observability instead of full telemetry stack

### Why these trade-offs were chosen

They maximize clarity, delivery speed, safety, and assignment fit.

---

## 21. Future Improvements

The following are intentionally outside MVP scope, but fit naturally into the architecture:

- specialist-facing authoring UI
- graph visual editor
- visual review/edit workflow
- richer evidence adapters
- simulation mode for specialists
- stronger regression evaluation
- audit trail for graph changes
- analytics dashboard
- multi-tenant auth and catalog management

---

## 22. Summary

This project is designed as a **lightweight prompt-driven assessment platform**.

A specialist defines assessment behavior outside of code.  
A compiler turns that input into a **canonical compiled graph**.  
A reusable runtime engine executes that graph, tracks user state, applies deterministic branching and scoring, and produces a personalized final report.
The graph is strict about logic, but flexible about phrasing.
Assessment nodes define what must be collected, while a lightweight conversational layer decides how to ask, when to confirm, and when a single answer already satisfies multiple nodes.

The architecture is intentionally small enough for MVP delivery, but structured enough to grow into a product platform.