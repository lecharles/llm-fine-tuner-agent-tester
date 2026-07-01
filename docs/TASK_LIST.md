# Task List

Fine-grained task tracker for the build, sliced by backend and frontend. 
More detailed than the roadmap: day-to-day working list.

## Phase 1: Backend foundation

### Setup

- [ ] Create /backend folder and a Python virtual environment (pipenv)
- [ ] Install FastAPI, Uvicorn, SQLAlchemy, Alembic, psycopg, Pydantic Settings, python-jose, passlib
- [ ] App entry point with a health-check route
- [ ] Confirm Swagger UI at /docs and ReDoc at /redoc
- [ ] Environment config for database URL and JWT secret
- [ ] Python .gitignore (virtualenv, pycache, env file)

### Database

- [ ] Create the Postgres database locally
- [ ] SQLAlchemy engine and session setup
- [ ] Alembic initialized and pointed at the database
- [ ] Base model and a get_db dependency

### Models (seven entities)

- [ ] User
- [ ] Dataset
- [ ] QAPair
- [ ] TrainingRun
- [ ] FineTunedModel
- [ ] ChatSession
- [ ] ChatMessage
- [ ] First migration generated and applied

### Auth

- [ ] Password hashing
- [ ] Sign up endpoint
- [ ] Log in endpoint issuing a JWT
- [ ] Current-user dependency that verifies the token
- [ ] Guests blocked from all write actions

### CRUD (schemas plus routes per resource)

- [ ] Datasets: schemas and CRUD routes
- [ ] QAPairs: schemas and CRUD routes, nested under dataset
- [ ] TrainingRuns: schemas and CRUD routes
- [ ] FineTunedModels: schemas and read/delete routes
- [ ] ChatSessions: schemas and CRUD routes
- [ ] ChatMessages: schemas and create/list routes
- [ ] Ownership enforced on every owned resource (write-time user override, read/edit/delete restricted to owner)

## Phase 2: Training (backend)

- [ ] Research spike: mlx-lm training API surface and how to invoke it
- [ ] Convert a dataset's Q/A pairs to mlx-lm training format (JSONL)
- [ ] Background job to run QLoRA training via mlx-lm
- [ ] Move training_runs.status through its lifecycle (queued, running, completed, failed)
- [ ] Fuse adapter and export to GGUF, write path to fine_tuned_models
- [ ] Endpoint to start training
- [ ] Endpoint to poll training status

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