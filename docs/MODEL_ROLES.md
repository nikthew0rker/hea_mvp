# Model Roles

This project uses Together-hosted models by role.

It does not assume that one universal model is best for:

- routing
- compilation
- review
- fast replies

## Current Provider

- `Together AI`

## Recommended Configuration

- `CONTROLLER_MODEL=MiniMaxAI/MiniMax-M2.5`
- `SPECIALIST_COMPILER_MODEL=zai-org/GLM-5`
- `EXTRACTION_MODEL=zai-org/GLM-5`
- `SPECIALIST_CRITIC_MODEL=MiniMaxAI/MiniMax-M2.5`
- `FAST_MODEL=MiniMaxAI/MiniMax-M2.5`

## Why This Split Exists

Different parts of the system have different failure modes.

- routing failures cause bad state transitions
- compilation failures corrupt the artifact structure
- critic failures let bad logic pass into publication
- fast-reply failures usually only hurt UX

So the model stack is separated by responsibility.

## Role 1: Controller / Analyst

Primary tasks:

- classify intent
- decide next graph action
- decide whether to prepare proposal
- ask clarification questions
- preserve stateful workflow discipline

Used on:

- specialist-side routing
- patient-side routing

Expected output style:

- strict structured JSON

Why `MiniMaxAI/MiniMax-M2.5` fits:

- good for agentic/tool-style decisions
- good JSON behavior on Together
- better fit for routing than a larger but JSON-weaker model

## Role 2: Specialist Compiler

Primary tasks:

- convert specialist source text into typed IR
- preserve option labels and numeric scores
- preserve framework semantics
- build structured questionnaire/anamnesis/rule graph specs

Expected output style:

- strict structured JSON matching the project IR

Why `zai-org/GLM-5` fits:

- good for decomposition and structured extraction
- works well as a compiler/parser role in this system

## Role 3: Extraction Helper

Primary tasks:

- support noisy extraction paths
- power helper parsing behavior
- provide backup/fallback structure extraction

Current note:

- some extraction logic is still heuristic and rule-based in project code
- this role is not the only extraction layer

## Role 4: Specialist Critic

Primary tasks:

- compare compiled spec to source intent
- detect omissions and distortions
- detect framework mismatch
- detect missing risk bands and malformed option structure
- decide whether apply/publish should be blocked

Expected output style:

- strict structured JSON

Why the critic is separate:

- generation and review have different incentives
- using the same pass for both is less reliable

## Role 5: Fast Reply

Primary tasks:

- short explanations
- summaries
- user-facing operational responses

Constraints:

- must not silently edit the artifact
- must not be used for JSON-critical steps if the model is not JSON-safe

## JSON Safety Policy

The system treats JSON reliability as a hard architectural concern.

Known JSON-unsafe models for this project:

- `openai/gpt-oss-120b`
- `openai/gpt-oss-20b`

Protection currently implemented:

- `TogetherAIClient.complete_json()` automatically reroutes known JSON-unsafe models to safer ones
- startup warnings are emitted when unsafe models are placed into JSON-critical roles

## Specialist Prompt Contracts

### Controller / Analyst contract

Must return:

- `next_action`
- `should_prepare_proposal`
- `should_apply_pending`
- `follow_up_question`
- `action_rationale`
- `confidence`
- `recognized_topic`

Behavioral rules:

- prefer `DISCUSS` when intent is ambiguous
- use edit/update only for explicit content-changing requests
- do not rewrite clinical content into final draft directly

### Compiler contract

Must return structured spec fields such as:

- `artifact_type`
- `topic`
- `framework`
- `questions`
- `risk_bands`
- `anamnesis_sections`
- `diagnostic_inputs`
- `rule_nodes`

Behavioral rules:

- preserve scores exactly
- do not collapse multi-option scored questions into yes/no
- keep missing data missing rather than inventing it

### Critic contract

Must return:

- `is_valid`
- `severity`
- `findings`
- `missing_information`
- `proposed_repairs`
- `should_block_apply`

Behavioral rules:

- review, do not rewrite
- block apply when score mappings or structure are lost
- report precise defects

## Operational Flow

Safe specialist flow:

`specialist message -> controller -> edit operation -> compiler -> critic -> proposal -> apply -> compile -> publish`

Important operational rule:

- `apply` updates the specialist draft
- `compile` builds a graph candidate
- only `publish` writes the artifact into the shared registry visible to the patient bot

So patient delivery begins only after:

`proposal -> apply -> compile -> publish`

## Guardrails Position

Guardrails is not part of the current runtime stack.

If added later, the right place for it is:

`model output -> guard/validation -> accept or re-ask`

It should complement:

- Pydantic schemas
- local validators
- critic pass

It should not replace the current typed pipeline architecture.
