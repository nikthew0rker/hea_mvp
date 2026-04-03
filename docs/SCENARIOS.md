# Demo Scenarios

This project currently targets two canonical demo scenarios for the assignment.

## Scenario 1: Diabetes Risk Screening

Type:

- `questionnaire`

Purpose:

- simple scored screening flow
- linear assessment
- easy to demonstrate prompt-driven authoring and patient delivery

Why it exists:

- this is the cleanest happy-path demo for the assignment
- it shows question extraction, scoring, risk bands, patient runtime, and report generation

Recommended specialist modes:

1. `single prompt mode`
- the specialist sends one large scenario prompt

2. `assistant mode`
- the specialist says they want a diabetes risk assessment
- the bot helps them define:
  - questions
  - answer options
  - scoring
  - risk bands
  - report style

Expected patient behavior:

- patient describes glucose / sugar / diabetes concern
- patient bot finds the published graph
- patient completes the questionnaire
- patient receives structured result and report
- after the result, the patient can ask for `подробный отчёт` and then `пдф?`, and `@hea_user_mvp_bot` will send the PDF report as a Telegram file

Single-prompt example:

```text
Create a questionnaire artifact for screening risk of type 2 diabetes in adults.

Use a FINDRISC-like scoring structure.

Questions:
1. Age
- <45 years — 0 points
- 45–54 years — 2 points
- 55–64 years — 3 points
- >64 years — 4 points

2. Body mass index
- <25 kg/m² — 0 points
- 25–30 kg/m² — 1 point
- >30 kg/m² — 3 points

3. Waist circumference
For men:
- <94 cm — 0 points
- 94–102 cm — 3 points
- >102 cm — 4 points

For women:
- <80 cm — 0 points
- 80–88 cm — 3 points
- >88 cm — 4 points

4. Daily physical activity
- Yes — 0 points
- No — 2 points

5. Vegetables, fruit, or berries every day
- Yes — 0 points
- No — 2 points

6. Antihypertensive medication
- No — 0 points
- Yes — 2 points

7. Previously elevated blood glucose
- No — 0 points
- Yes — 2 points

8. Family history of diabetes
- No — 0 points
- Extended family — 3 points
- First-degree relative — 5 points

Scoring:
- sum all option scores

Risk bands:
- <7 -> low risk
- 7–11 -> slightly elevated risk
- 12–14 -> moderate risk
- 15–20 -> high risk
- >20 -> very high risk

Report:
- show total score
- show risk category
- explain that this is a screening result and only a blood test can confirm diabetes or prediabetes
- for elevated or higher risk, recommend planned clinician follow-up and formal testing such as blood glucose or A1C
- include practical prevention-oriented next steps: physical activity, nutrition, and weight management
- include a disclaimer that this is screening, not a diagnosis
```

## Scenario 2: Burnout Risk Screening

Type:

- `questionnaire`

Framework:

- `burnout`

Purpose:

- branching assessment demo
- shows adaptive logic rather than only linear scoring

Why it exists:

- the assignment explicitly asks for adaptive logic
- this scenario demonstrates that the next question can depend on the previous answer

Current branching design:

- if exhaustion is rare, the runtime can skip the exhaustion follow-up
- if cynicism/detachment is absent, the runtime can skip the interpersonal impact follow-up

Expected specialist value:

- the specialist can provide a fully specified branching prompt
- or the bot can help them design the branching structure interactively

Recommended specialist flow in the current MVP:

1. send the branching questions first
2. apply the proposal
3. send risk bands and report requirements as a second update
4. apply the proposal again
5. run `compile`
6. run `publish`

Why this is currently recommended:

- the specialist pipeline is reliable on branching question extraction
- risk bands and report requirements may be added more reliably as a focused follow-up update
- this gives a more stable demo path for the assignment than trying to force the entire burnout scenario through one large message every time
- after completion, the patient can request a detailed report and then ask for `pdf` / `пдф`, and the bot will upload the report into the chat as a file

Single-prompt example:

```text
Create a questionnaire artifact for screening burnout risk in working adults.

Use adaptive branching. The next question must depend on the previous answer.

Questions:
1. How often do you feel emotionally exhausted after work?
- Rarely — 0 points -> go to question 3
- Sometimes — 1 point -> go to question 2
- Often — 2 points -> go to question 2

2. When exhaustion is present, does rest usually restore your energy by the next day?
- Yes — 0 points -> go to question 3
- Partly — 1 point -> go to question 3
- No — 2 points -> go to question 3

3. Has your work become more cynical, detached, or emotionally numb recently?
- No — 0 points -> go to question 5
- A little — 1 point -> go to question 4
- Clearly yes — 2 points -> go to question 4

4. Is this affecting your relationships with colleagues, patients, or clients?
- No — 0 points -> go to question 5
- Sometimes — 1 point -> go to question 5
- Often — 2 points -> go to question 5

5. Is your concentration or work effectiveness lower than usual?
- No — 0 points
- Sometimes — 1 point
- Often — 2 points

Scoring:
- sum all option scores that were actually asked

Risk bands:
- 0–2 -> low burnout risk
- 3–5 -> moderate burnout risk
- 6+ -> high burnout risk

Report:
- summarize exhaustion
- summarize detachment
- summarize work impact
- use supportive wording
- do not diagnose depression or anxiety
- state that burnout is treated here as a work-related screening construct, not a formal medical diagnosis
- for moderate or high risk, recommend reviewing workload and recovery and considering clinician or mental health follow-up if symptoms persist or worsen
- if functioning is worsening substantially, recommend timely in-person support rather than relying only on the bot
```

Two-step demo flow for the current implementation:

Step 1, send questions and branching:

```text
Create a questionnaire artifact for screening burnout risk in working adults.

Use adaptive branching. The next question must depend on the previous answer.

Questions:
1. How often do you feel emotionally exhausted after work?
- Rarely — 0 points -> go to question 3
- Sometimes — 1 point -> go to question 2
- Often — 2 points -> go to question 2

2. When exhaustion is present, does rest usually restore your energy by the next day?
- Yes — 0 points -> go to question 3
- Partly — 1 point -> go to question 3
- No — 2 points -> go to question 3

3. Has your work become more cynical, detached, or emotionally numb recently?
- No — 0 points -> go to question 5
- A little — 1 point -> go to question 4
- Clearly yes — 2 points -> go to question 4

4. Is this affecting your relationships with colleagues, patients, or clients?
- No — 0 points -> go to question 5
- Sometimes — 1 point -> go to question 5
- Often — 2 points -> go to question 5

5. Is your concentration or work effectiveness lower than usual?
- No — 0 points
- Sometimes — 1 point
- Often — 2 points
```

Then:

```text
apply proposal
```

Step 2, send risk bands and report requirements:

```text
Add burnout risk bands for this questionnaire.

Scoring:
- sum all option scores that were actually asked

Risk bands:
- 0–2 -> low burnout risk
- 3–5 -> moderate burnout risk
- 6+ -> high burnout risk

Report:
- summarize exhaustion
- summarize detachment
- summarize work impact
- use supportive wording
- do not diagnose depression or anxiety
```

Then:

```text
apply proposal
compile
publish
```

## Why These Two Scenarios

Together they demonstrate the two strongest claims of the MVP:

1. `Diabetes` proves the system can do a practical prompt-driven screening questionnaire with scoring and reporting.
2. `Burnout` proves the system can do adaptive branching rather than only static question lists.

## Full Demo Script: Diabetes

Telegram bots:

- Specialist bot: `@hea_specialist_mvp_bot`
- User bot: `@hea_user_mvp_bot`

Recommended stable flow in the current MVP:

### Specialist bot script

1. Start:

```text
/start
```

2. Send the diabetes questionnaire prompt:

```text
Create a questionnaire artifact for screening risk of type 2 diabetes in adults.

Use a FINDRISC-like scoring structure.

Questions:
1. Age
- <45 years — 0 points
- 45–54 years — 2 points
- 55–64 years — 3 points
- >64 years — 4 points

2. Body mass index
- <25 kg/m² — 0 points
- 25–30 kg/m² — 1 point
- >30 kg/m² — 3 points

3. Waist circumference
For men:
- <94 cm — 0 points
- 94–102 cm — 3 points
- >102 cm — 4 points

For women:
- <80 cm — 0 points
- 80–88 cm — 3 points
- >88 cm — 4 points

4. Daily physical activity
- Yes — 0 points
- No — 2 points

5. Vegetables, fruit, or berries every day
- Yes — 0 points
- No — 2 points

6. Antihypertensive medication
- No — 0 points
- Yes — 2 points

7. Previously elevated blood glucose
- No — 0 points
- Yes — 2 points

8. Family history of diabetes
- No — 0 points
- Extended family — 3 points
- First-degree relative — 5 points

Scoring:
- sum all option scores

Risk bands:
- <7 -> low risk
- 7–11 -> slightly elevated risk
- 12–14 -> moderate risk
- 15–20 -> high risk
- >20 -> very high risk

Report:
- show total score
- show risk category
- provide short interpretation
- include a disclaimer that this is screening, not a diagnosis
```

3. Apply the proposal:

```text
apply proposal
```

4. Compile:

```text
compile
```

5. Publish:

```text
publish
```

### User bot script

1. Start:

```text
/start
```

2. Search with a natural complaint:

```text
I am worried about blood sugar
```

3. Confirm:

```text
yes
```

4. Complete the questionnaire with any valid path, for example:

```text
1
2
1
2
1
1
2
1
```

5. Ask for explanation or report:

```text
explain
```

or

```text
detailed report
```

Expected outcome:

- patient bot finds the published diabetes graph
- runs a scored questionnaire
- returns score, risk category, interpretation, and next steps
- HTML report is available at `GET /report/{conversation_id}`
- PDF report is available at `GET /report/{conversation_id}.pdf`

## Full Demo Script: Burnout

Telegram bots:

- Specialist bot: `@hea_specialist_mvp_bot`
- User bot: `@hea_user_mvp_bot`

Recommended stable flow in the current MVP:

### Specialist bot script

1. Start:

```text
/start
```

2. Send the burnout branching prompt:

```text
Create a questionnaire artifact for screening burnout risk in working adults.

Use adaptive branching. The next question must depend on the previous answer.

Questions:
1. How often do you feel emotionally exhausted after work?
- Rarely — 0 points -> go to question 3
- Sometimes — 1 point -> go to question 2
- Often — 2 points -> go to question 2

2. When exhaustion is present, does rest usually restore your energy by the next day?
- Yes — 0 points -> go to question 3
- Partly — 1 point -> go to question 3
- No — 2 points -> go to question 3

3. Has your work become more cynical, detached, or emotionally numb recently?
- No — 0 points -> go to question 5
- A little — 1 point -> go to question 4
- Clearly yes — 2 points -> go to question 4

4. Is this affecting your relationships with colleagues, patients, or clients?
- No — 0 points -> go to question 5
- Sometimes — 1 point -> go to question 5
- Often — 2 points -> go to question 5

5. Is your concentration or work effectiveness lower than usual?
- No — 0 points
- Sometimes — 1 point
- Often — 2 points

Scoring:
- sum all option scores that were actually asked

Risk bands:
- 0–2 -> low burnout risk
- 3–5 -> moderate burnout risk
- 6+ -> high burnout risk

Report:
- summarize exhaustion
- summarize detachment
- summarize work impact
- use supportive wording
- do not diagnose depression or anxiety
```

3. Apply the proposal:

```text
apply proposal
```

4. If the proposal was created without risk bands in the current bot state, send the focused follow-up update:

```text
Add burnout risk bands for this questionnaire.

Scoring:
- sum all option scores that were actually asked

Risk bands:
- 0–2 -> low burnout risk
- 3–5 -> moderate burnout risk
- 6+ -> high burnout risk

Report:
- summarize exhaustion
- summarize detachment
- summarize work impact
- use supportive wording
- do not diagnose depression or anxiety
```

5. Apply again if a second proposal was created:

```text
apply proposal
```

6. Compile:

```text
compile
```

7. Publish:

```text
publish
```

### User bot script

1. Start:

```text
/start
```

2. Search with a natural complaint:

```text
I think I may be burning out at work
```

3. Confirm:

```text
yes
```

4. Example branching run:

```text
2
3
2
1
2
```

This path means:

- `q1 = Sometimes` -> go to `q2`
- `q2 = No` -> go to `q3`
- `q3 = A little` -> go to `q4`
- `q4 = No` -> go to `q5`
- `q5 = Sometimes`

5. Ask for a full report:

```text
detailed report
```

Expected outcome:

- patient bot runs the adaptive branching burnout questionnaire
- skips questions according to `next_question_id`
- returns score, burnout risk category, personalized summary, and safe next steps
- HTML report is available at `GET /report/{conversation_id}`
- PDF report is available at `GET /report/{conversation_id}.pdf`

## Evidence Notes For Report Recommendations

These scenarios use patient-safe, non-diagnostic report wording informed by official public sources.

### Burnout

Used to shape the burnout report:

- WHO describes burnout as an occupational phenomenon rather than a medical condition and defines it through:
  - exhaustion
  - mental distance / cynicism
  - reduced professional efficacy
- Mayo Clinic patient guidance supports practical next steps such as:
  - reviewing workload and options at work
  - seeking support
  - stress-reduction practices
  - exercise and sleep
  - talking to a healthcare or mental health professional when symptoms persist

Sources:

- WHO: https://www.who.int/standards/classifications/frequently-asked-questions/burn-out-an-occupational-phenomenon
- WHO: https://www.who.int/news/item/28-05-2019-burn-out-an-occupational-phenomenon-international-classification-of-diseases
- WHO mental health at work: https://www.who.int/news-room/fact-sheets/detail/mental-health-at-work
- Mayo Clinic burnout overview: https://www.mayoclinic.org/healthy-lifestyle/adult-health/in-depth/burnout/art-20046642

### Diabetes

Used to shape the diabetes report:

- CDC and NIDDK stress that risk tests are screening tools and that only blood testing can confirm diabetes or prediabetes
- CDC prevention materials support next steps around:
  - physical activity
  - healthy eating
  - weight management
  - clinician follow-up
- NIDDK explains formal diagnostic pathways through A1C and blood glucose testing

Sources:

- CDC Prediabetes Risk Test background: https://www.cdc.gov/diabetes/takethetest/about-the-test.html
- CDC prevention messaging: https://www.cdc.gov/diabetes/communication-resources/prediabetes-statistics.html
- NIDDK Diabetes Risk Test: https://www.niddk.nih.gov/health-information/diabetes/overview/risk-factors-type-2-diabetes/diabetes-risk-test
- NIDDK diagnosis/testing: https://www.niddk.nih.gov/health-information/diabetes/overview/tests-diagnosis
