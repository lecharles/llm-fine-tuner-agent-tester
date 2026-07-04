# Roadmap

Phased delivery plan LLM Fine Tuner & Agent Tester app. 
Working plan: where we are, what is next, and what is parked.

## Status

- [x] Phase 0: Planning
- [x] Phase 1: Backend foundation
- [x] Phase 2: Training
- [x] Phase 3: Dataset generation
- [ ] Phase 4: Compare chat
- [ ] Phase 5: Polish and deploy

## Phases

### Phase 0: Planning

- [x] README with key terms
- [x] ERD (diagram plus doc)
- [x] User stories (table with status column)
- [x] Wireframes for the main pages

### Phase 1: Backend foundation

- [x] FastAPI skeleton, running locally
- [x] Swagger UI auto-generated at /docs, ReDoc at /redoc
- [x] PostgreSQL wired via SQLAlchemy
- [x] Migrations via Alembic
- [x] The seven entities from the ERD
- [x] JWT authentication
- [x] Full CRUD on owned entities (datasets and qa-pairs; other entities via feature behavior)
- [x] Ownership-based authorization

### Phase 2: Training (hero feature)

- [x] Fine-tuning via mlx-lm on Apple Silicon, QLoRA by default
- [x] Background job started from the API, status tracked on training_runs
- [x] Llama 3.2 1B default, 3B optional

### Phase 3: Dataset generation

- [x] Generate question-answer pairs from a plain-English use case description via an LLM API
- [x] Optional Hugging Face dataset import
- [x] Research spike: dataset selection
- [x] Research spike: prompt strategy for Q/A generation

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

- [ ] Training method selection: QLoRA 4-bit (default), LoRA 16-bit, full fine-tune, continued pretraining, mapped to what mlx-lm supports (4-bit base, fp16 base, --fine-tune-type full, text-format data)
- [ ] Learning rate, context length (max sequence length)
- [ ] LoRA rank, alpha (scale), dropout, target modules, number of layers
- [ ] Batch size, gradient accumulation, gradient checkpointing (memory levers, matter more for the 3B)
- [ ] RS-LoRA and LoftQ: verify mlx-lm support first, these may be out of scope for the mlx-lm engine
- [ ] Keep the default flow simple, iters as the single training knob, per the "easy as a guitar tuner" value prop

### Training run visibility

- [ ] A clear, simple overview of training runs and their status (queued, running, completed, failed), easy to scan at a glance
- [ ] Live status and loss for the current run, plus a history view of past runs (match Current Run and History tabs in the reference UI)

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