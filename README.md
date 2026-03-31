# Hea MVP

Hea MVP is a platform for creating and running **assessment graphs**: structured risk assessments, screenings, questionnaires, and other conversational flows that are first designed by a specialist and then completed by an end user through a conversational assistant.

The project is split into two major domains:

1. **Specialist-side authoring** — the specialist creates the graph:
   - sends source material, guidelines, tables, noisy text, or a plain description;
   - the bot extracts structure into a draft;
   - the draft is edited;
   - the graph is compiled;
   - the graph is published into the library.

2. **Patient-side orchestration** — the user talks to the bot:
   - starts with free conversation;
   - the bot analyzes the request, goal, or problem;
   - searches for a suitable graph in the library;
   - proposes an assessment;
   - gets consent;
   - runs the graph runtime;
   - returns the result;
   - goes back to free conversation.

The project is **not tied to a single graph** and is architecturally designed for a collection of assessments.

---

## What the system can do

### For specialists
- accept a free-form assessment description;
- extract:
  - topic,
  - questions,
  - scoring logic,
  - risk bands,
  - report requirements,
  - safety requirements;
- edit the draft in natural language;
- show preview, questions, scoring, and risk bands;
- compile the draft into a runtime-ready graph;
- publish the graph into the library.

### For end users
- start with a normal conversation instead of a rigid questionnaire;
- describe a problem or intention in free form;
- receive a relevant assessment proposal;
- give consent to proceed;
- complete the assessment step by step;
- receive a final result based on graph logic;
- continue free conversation after completion.

---

## Architecture

## High-level view

```text
Specialist Bot
  ↓
Definition Agent
  ↓
Compiler Agent
  ↓
Publish Handoff
  ├── active_graph.json
  └── graph_registry.json
                ↓
         Patient Controller
                ├── Conversation analysis
                ├── Graph search
                ├── Consent
                ├── Graph runtime
                └── Result / free conversation
                ↓
             User Bot
```

---

## Key components

### 1. Specialist Bot
Telegram bot for the specialist.  
Works as a controller-based copilot over the current draft.

Responsibilities:
- receives source materials;
- understands what the specialist wants to do;
- calls the definition agent;
- shows the current draft;
- triggers compile and publish.

### 2. Definition Agent
Service for extracting and editing assessment structure.

Responsibilities:
- normalizes noisy input;
- extracts candidate questions, scoring, and risk bands;
- merges the result with the current draft;
- applies natural-language edits.

### 3. Compiler Agent
Transforms a draft into a runtime-ready graph.

Responsibilities:
- checks compile readiness;
- builds the graph payload;
- generates a **unique graph_id**;
- preserves data required for patient-side runtime.

### 4. Publish Handoff
Publishes the graph into storage.

Responsibilities:
- updates `active_graph.json`;
- adds the graph to `graph_registry.json`;
- makes the graph available for patient-side discovery and runtime.

### 5. Graph Registry
Library of published graphs.

Each graph is stored with metadata such as:
- `graph_id`
- `title`
- `topic`
- `description`
- `tags`
- `entry_signals`
- `questions_count`
- `estimated_time_minutes`
- `graph`

### 6. Patient Controller / Orchestrator
The main brain of the user-side bot.

It works in several modes:
- `free_conversation`
- `awaiting_consent`
- `assessment_in_progress`
- `paused_assessment`
- `post_assessment`

Responsibilities:
- analyzes user messages;
- searches the library;
- proposes an assessment;
- gets consent;
- runs the runtime;
- returns the conversation to free mode.

### 7. Patient Graph Runtime
Deterministic execution engine.

Responsibilities:
- asks questions;
- accepts normalized answers;
- advances the graph;
- computes score;
- determines result / risk band;
- completes the assessment.

### 8. User Bot
Telegram bot for the end user.  
It does not contain business logic and only proxies messages to the patient controller.

### 9. Report Agent
Generates a summary/result after assessment completion.

### 10. Evaluation Agent
Layer for checks and QA:
- integrity checks;
- graph validation;
- result consistency;
- future regression checks.

---

## Data structures

### Draft
The working draft used by the specialist.

Usually contains:
- `understood`
- `candidate_questions`
- `candidate_scoring_rules`
- `candidate_risk_bands`
- `candidate_report_requirements`
- `candidate_safety_requirements`
- `missing_fields`

### Compiled graph
Runtime-ready object produced after compile.

Usually contains:
- `graph_version_id`
- `title`
- `topic`
- `questions` or `nodes`
- `risk_bands`
- `scoring`
- `source_draft`

### Graph registry entry
One graph library record.

Usually contains:
- `graph_id`
- `published_at`
- `published`
- `metadata`
- `graph`

### Patient session
The state of the user conversation.

Usually contains:
- `mode`
- `language`
- `selected_graph_id`
- `discovered_graphs`
- `consent_status`
- `assessment_state`
- `last_result`
- `history`

---

## Data storage

At the current stage, the project uses file-based storage.

Main files:
- `data/active_graph.json`
- `data/graph_registry.json`
- `data/patient_sessions.json`

Why this is acceptable for MVP:
- simple;
- transparent;
- easy to debug;
- easy to repair manually;
- does not block fast architectural iteration.

JSON files must:
- be created only if missing;
- not be overwritten on startup;
- be written atomically.

---

## Product boundaries

The system is an **assessment platform**, not a full medical advisor.

It may:
- explain an assessment;
- guide the user through the graph;
- present a result defined by graph logic;
- help choose another assessment.

It must not:
- diagnose;
- prescribe treatment;
- recommend medication;
- drift into unrestricted medical consultation.

---

## How to run the project

## Requirements
- Docker
- Docker Compose
- Together AI API key
- two Telegram bot tokens:
  - specialist bot
  - user bot

---

## 1. Prepare `.env`

Copy the example:

```bash
cp .env.example .env
```

Fill in the variables:

```env
TOGETHER_API_KEY=your_together_api_key
TOGETHER_MODEL=Qwen/Qwen3.5-9B

SPECIALIST_CONTROLLER_MODEL=zai-org/GLM-5
PATIENT_CONTROLLER_MODEL=zai-org/GLM-5
DEFINITION_AGENT_MODEL=Qwen/Qwen3.5-397B-A17B
RUNTIME_AGENT_MODEL=Qwen/Qwen3.5-9B
REPORT_AGENT_MODEL=Qwen/Qwen3.5-9B
EVALUATION_AGENT_MODEL=Qwen/Qwen3.5-9B

SPECIALIST_BOT_TOKEN=your_specialist_bot_token
USER_BOT_TOKEN=your_user_bot_token

DEFINITION_AGENT_URL=http://definition-agent:8000
COMPILER_AGENT_URL=http://compiler-agent:8000
RUNTIME_AGENT_URL=http://runtime-agent:8000
REPORT_AGENT_URL=http://report-agent:8000
EVALUATION_AGENT_URL=http://evaluation-agent:8000
PATIENT_CONTROLLER_URL=http://patient-controller:8000
```

---

## 2. Start the services

Recommended startup:

```bash
docker compose down --remove-orphans
docker compose build --no-cache
docker compose up
```

---

## 3. What should be running

Usually the following services are started:
- `definition-agent`
- `compiler-agent`
- `runtime-agent` (legacy / optional depending on current flow)
- `report-agent`
- `evaluation-agent`
- `patient-controller`
- `specialist-bot`
- `user-bot`

---

## How to use the project

## Specialist workflow

### Step 1. Open the specialist bot
Start a dialogue with the specialist bot.

### Step 2. Send material
You can send:
- an assessment description;
- a guideline;
- a scoring table;
- noisy text;
- an article;
- a question structure.

Example:
> I want an assessment for type 2 diabetes risk.  
> 8 questions, final result based on total score, several risk bands.

### Step 3. Check what the bot understood
You can ask:
- what did you understand?
- show questions
- show scoring
- show risk bands

### Step 4. Apply edits
For example:
- change question 3;
- add help text;
- fix scoring;
- change wording.

### Step 5. Compile
Ask for compile.

Expected result:
- `status=compiled`
- a new `graph_id`

### Step 6. Publish
Ask for publish.

After publish:
- the graph appears in `active_graph.json`
- the graph is added to `graph_registry.json`

---

## User workflow

### Step 1. Open the user bot
The user starts with free conversation:
> Hi  
> I often feel tired and want to understand whether there are any risks

### Step 2. Patient controller analyzes the request
The system searches for relevant graphs in the library.

### Step 3. The bot proposes an assessment
For example:
> Based on what you described, a “Type 2 Diabetes Risk Assessment” may be suitable.  
> It is 8 questions and about 3 minutes.  
> Would you like to take it now?

### Step 4. The user gives consent
For example:
> yes

### Step 5. Runtime starts
The bot asks questions according to the graph.

### Step 6. Result is computed
After completion, the bot shows:
- score
- category / risk band
- short summary

### Step 7. Return to free conversation
After the result, the user can ask:
- what else can you do?
- is there another assessment?
- explain the result

---

## Recommended MVP workflow

If you are starting from an empty system:

1. start the services;
2. build at least one graph through the specialist bot;
3. compile;
4. publish;
5. verify that:
   - `data/active_graph.json` exists,
   - `data/graph_registry.json` contains an entry;
6. open the user bot;
7. start a free-form conversation;
8. verify that the bot:
   - does not start an assessment without consent,
   - can propose a relevant graph,
   - starts assessment only after acceptance.

---

## Health checks and inspection

## Check containers

```bash
docker compose ps
```

## Check active graph

```bash
cat data/active_graph.json
```

## Check graph registry

```bash
cat data/graph_registry.json
```

## Check patient sessions

```bash
cat data/patient_sessions.json
```

---

## Typical problems

## 1. User bot jumps straight to question 1
Cause:
- old version of patient controller / user bot;
- orchestration patch not applied;
- old containers were not rebuilt.

Fix:
```bash
docker compose down --remove-orphans
docker compose build --no-cache patient-controller user-bot
docker compose up
```

---

## 2. Bot cannot find assessments
Cause:
- graph library is empty;
- there is only an old `active_graph.json`, but no entries in `graph_registry.json`.

Fix:
- compile + publish at least one graph again;
- inspect `data/graph_registry.json`.

---

## 3. Graph has broken options / risk bands
Cause:
- old broken compile/publish payload.

Fix:
- recompile the graph with the new compiler;
- or manually repair the registry entry;
- or use a repair script.

---

## 4. User bot feels too rigid and questionnaire-like
Cause:
- the system is still running in old `single active graph runner` mode;
- orchestration layer was not applied or did not reach the containers;
- graph runtime payload is too poor.

Fix:
- use patient orchestration architecture;
- inspect graph registry;
- strengthen compiler output.

---

## Further evolution

The next logical steps:

### 1. Move from JSON storage to SQLite/PostgreSQL
To store:
- graph versions
- registry
- specialist sessions
- patient sessions
- audit trail

### 2. Improve graph search
Add:
- semantic search
- embedding similarity
- ranking by entry signals
- multi-candidate selection

### 3. Build a full runtime contract
So the compiler produces:
- node types
- normalization rules
- validation rules
- help text
- why-it-matters text
- branching rules

### 4. Add UI
- specialist authoring UI
- graph browser
- graph preview
- runtime inspector

---

## Documentation

Full technical documentation is stored in `/docs`.

Recommended reading order:
1. `ARCHITECTURE.md`
2. `SERVICES.md`
3. `SPECIALIST_ARCHITECTURE.md`
4. `PATIENT_ORCHESTRATION_ARCHITECTURE.md`
5. `PATIENT_RUNTIME_CONTRACT.md`
6. `graph-registry.md`
7. `graph-search.md`

---

## In short

Hea MVP is not just a questionnaire bot and not just a set of CRUD services.

It is an MVP of a platform where:
- a specialist **creates an assessment graph**,
- the system **publishes it into a library**,
- the user **starts with a natural conversation**,
- the orchestrator **finds a suitable graph**,
- the runtime **executes the assessment**,
- the system **returns the result**,
- and the dialogue goes back to free conversation.
