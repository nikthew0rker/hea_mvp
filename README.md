# Hea MVP v2 Scaffold

This scaffold creates:

- two Telegram bots:
  - specialist bot
  - user bot

- five internal agents:
  - definition agent
  - compiler agent
  - runtime agent
  - report agent
  - evaluation agent

- one shared Together AI client
- one uv-ready Python project
- Dockerfiles and docker-compose for local orchestration

## Setup with uv

```bash
uv sync
cp .env.example .env
```

## Run locally with uv

```bash
./run_definition_agent.sh
./run_compiler_agent.sh
./run_runtime_agent.sh
./run_report_agent.sh
./run_evaluation_agent.sh
./run_specialist_bot.sh
./run_user_bot.sh
```

## Run with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```
