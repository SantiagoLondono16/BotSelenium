# Project instructions

This repository contains a technical test with:
- FastAPI backend
- Selenium RPA bot
- PostgreSQL
- Docker Compose
- Optional frontend (not required)

## Non-negotiable rules
- Do not hardcode credentials or secrets
- Use environment variables and provide .env.example
- Prefer clear modular architecture
- Use explicit waits in Selenium
- Avoid fixed sleeps as the main synchronization method
- Add structured logging
- Handle timeouts and expected failures
- Keep responsibilities separated
- Do not invent CSS/XPath selectors if they are not verified
- Write concise, production-like code
- Favor maintainability over cleverness

## API contract
Required endpoints:
- POST /rpa/extract
- GET /jobs
- GET /jobs/{id}
- GET /records
- GET /records/{id}

## Desired architecture
- app/api
- app/services
- app/rpa
- app/db
- app/schemas
- app/core
- tests

## Working style
- Always propose a short plan before major changes
- Implement one module at a time
- Explain assumptions
- After each task, list what remains pending