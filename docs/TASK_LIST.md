# Task List

Fine-grained task tracker for the build, sliced by backend and frontend. 
More detailed than the roadmap: day-to-day working list.

## Phase 1: Backend foundation

### Setup

- [x] Create /backend folder and a Python virtual environment (pipenv)
- [x] Install FastAPI, Uvicorn, SQLAlchemy, Alembic, psycopg, Pydantic Settings, python-jose, passlib
- [x] App entry point with a health-check route
- [x] Confirm Swagger UI at /docs and ReDoc at /redoc
- [x] Environment config for database URL and JWT secret
- [x] Python .gitignore (virtualenv, pycache, env file)

### Database

- [x] Create the Postgres database locally
- [x] SQLAlchemy engine and session setup
- [x] Alembic initialized and pointed at the database
- [x] Base model and a get_db dependency

### Models (seven entities)

- [x] User
- [x] Dataset
- [x] QAPair
- [x] TrainingRun
- [x] FineTunedModel
- [x] ChatSession
- [x] ChatMessage
- [x] First migration generated and applied

### Auth

- [x] Password hashing
- [x] Sign up endpoint
- [x] Log in endpoint issuing a JWT
- [x] Current-user dependency that verifies the token
- [x] Guests blocked from all write actions

### CRUD (schemas plus routes per resource)

- [x] Datasets: schemas and CRUD routes
- [x] QAPairs: schemas and CRUD routes, nested under dataset
- [ ] TrainingRuns: created by the training feature in Phase 2, not generic CRUD
- [ ] FineTunedModels: created by the training feature in Phase 2, not generic CRUD
- [ ] ChatSessions: created by the compare-chat feature in Phase 4, not generic CRUD
- [ ] ChatMessages: created by the compare-chat feature in Phase 4, not generic CRUD
- [x] Ownership enforced on every owned resource (write-time user override, read/edit/delete restricted to owner)

## Phase 2: Training (backend)

- [x] Research spike: mlx-lm training API surface and how to invoke it
- [x] Validate the training pipeline on-device (train + fuse); GGUF/Ollama serving moved to Phase 4
- [x] Convert a dataset's Q/A pairs to mlx-lm training format (JSONL)
- [x] Background job to run QLoRA training via mlx-lm
- [x] Move training_runs.status through its lifecycle (queued, running, completed, failed)
- [x] Fuse adapter (GGUF export deferred to Phase 4; fuse-only for now), write path to fine_tuned_models
- [x] Endpoint to start training
- [x] Endpoint to poll training status

## Phase 3: Dataset generation (backend)

- [ ] Research spike: pick a Hugging Face Q/A dataset for the preset option
- [ ] Research spike: prompt strategy for generating Q/A pairs from a use-case description
- [ ] LLM API integration for generation
- [ ] Endpoint: generate N pairs from a description, persist to a dataset
- [ ] Endpoint: import a dataset from Hugging Face

## Phase 4: Compare chat (backend)

- [ ] Serve the fine-tuned model locally via Ollama and call it
- [ ] Integrate two hosted comparison models
- [ ] Endpoint: send a prompt, fan out to three models, persist the user message plus three replies
- [ ] Endpoints: list chat sessions and their messages

## Frontend (React, TypeScript, Vite)

Starts once the API exposes real endpoints, overlapping Phases 2 and 3.

- [ ] Scaffold Vite plus React plus TypeScript
- [ ] App shell with sidebar navigation and routing
- [ ] Auth pages (login, signup) and token handling
- [ ] Datasets: list, detail, create, generate, edit pairs
- [ ] Train: config form, start, live status
- [ ] Models: list, export, delete
- [ ] Compare chat: three-column layout, send prompt
- [ ] Light and dark theme

## Phase 5: Polish and deploy

- [ ] Visual theme pass, cohesive layout
- [ ] Accessibility: WCAG AA contrast, alt text on images, link-based navigation
- [ ] Deploy the web shell online
- [ ] README screenshots and deployed link

## Presentation prep (before Tuesday)

- [ ] Pre-stage demo data and tokens for a flawless live run
- [ ] Rehearse the demo path end to end
- [ ] FastAPI pitch, three bullets
- [ ] React and TypeScript pitch, three bullets
- [ ] Aha moments from the learning journal
- [ ] Five-minute presentation flow