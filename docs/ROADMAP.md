# Roadmap

Phased delivery plan LLM Fine Tuner & Agent Tester app. 
Working plan: where we are, what is next, and what is parked.

## Status

- [x] Phase 0: Planning
- [ ] Phase 1: Backend foundation
- [ ] Phase 2: Training
- [ ] Phase 3: Dataset generation
- [ ] Phase 4: Compare chat
- [ ] Phase 5: Polish and deploy

## Phases

### Phase 0: Planning

- [x] README with key terms
- [x] ERD (diagram plus doc)
- [x] User stories (table with status column)
- [x] Wireframes for the main pages

### Phase 1: Backend foundation

- [ ] FastAPI skeleton, running locally
- [ ] Swagger UI auto-generated at /docs, ReDoc at /redoc
- [ ] PostgreSQL wired via SQLAlchemy
- [ ] Migrations via Alembic
- [ ] The seven entities from the ERD
- [ ] JWT authentication
- [ ] Full CRUD on owned entities
- [ ] Ownership-based authorization

### Phase 2: Training (hero feature)

- [ ] Fine-tuning via mlx-lm on Apple Silicon, QLoRA by default
- [ ] Background job started from the API, status tracked on training_runs
- [ ] Llama 3.2 1B default, 3B optional

### Phase 3: Dataset generation

- [ ] Generate question-answer pairs from a plain-English use case description via an LLM API
- [ ] Optional Hugging Face dataset import
- [ ] Research spike: dataset selection
- [ ] Research spike: prompt strategy for Q/A generation

### Phase 4: Compare chat

- [ ] Three-way chat: fine-tuned model plus two comparison models
- [ ] Fine-tuned model served locally (GGUF via Ollama)
- [ ] Comparison models via hosted APIs

### Phase 5: Polish and deploy

- [ ] Visual theme and cohesive layout
- [ ] Accessibility pass (WCAG AA)
- [ ] Link-based navigation
- [ ] Deploy the web shell online (training stays local, Apple Silicon requirement)

### Frontend (React, TypeScript, Vite)

- [ ] Scaffold Vite plus React plus TypeScript
- [ ] Consume the documented API
- [ ] Starts once the API exposes real endpoints, overlapping Phases 2 and 3

### Presentation and demo prep (before Tuesday)

- [ ] Pre-stage demo data and tokens for a flawless live run
- [ ] Rehearse the demo path end to end
- [ ] FastAPI pitch in three bullets
- [ ] React and TypeScript pitch in three bullets
- [ ] Aha moments to highlight (from the learning journal)
- [ ] Five-minute presentation flow

## Backlog and parking lot

Ideas captured so they are not forgotten. Not scheduled for MVP.

### Advanced training mode

Expose the full hyperparameter surface behind an Advanced panel, stored in an advanced_config JSON column on training_runs.

- [ ] Learning rate, context length
- [ ] LoRA rank, alpha, dropout, target modules
- [ ] RS-LoRA, LoftQ, and other options mlx-lm exposes
- [ ] Keep the default flow to epochs only as per "easy as a guitar tuner" value prop

### Repo strategy

This repo is the flagship. Later, extract dedicated showcase repos.

- [ ] API Agents repo: clean API primitives and an SDK-style surface, developer experience focus
- [ ] API Infrastructure repo: enterprise controls (API keys and access control, rate limiting and spend limits, usage metering and cost dashboards, audit logs, data governance, identity flows such as SSO/SAML and SCIM, RBAC with admin tooling)

### Platform expansion

- [ ] React Native build for iOS and Android from the same core
- [ ] Native macOS app
- [ ] Swift refactor (long horizon)

### Brand and design

- [ ] Guitar-tuner motif: cartoony logo, VU meter, Fender Stratocaster styling, tuner needle
- [ ] Style the Swagger UI to match the app theme
- [ ] Polished, keyboard-first UI with tight spacing, a restrained palette, and purposeful motion
- [ ] Light mode and dark mode

### Product depth

- [ ] In-app guides explaining fine-tuning, dataset design, hyperparameters, export, and testing
- [ ] Additional small model families beyond Llama

### Sharing and visibility

- [ ] Owner can mark a dataset public or private (is_public flag on datasets)
- [ ] Owner can mark a fine-tuned model public or private (is_public flag on fine_tuned_models)
- [ ] Read and list queries include public items from other users; writes stay owner-only
- [ ] Authorization rule: read if owner OR public; create, update, delete if owner only
- [ ] Supports the open-source, shareable spirit of the project