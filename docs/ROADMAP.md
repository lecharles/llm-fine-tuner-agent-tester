# Roadmap

Phased delivery plan LLM Fine Tuner & Agent Tester app. 
Working plan: where we are, what is next, and what is parked.

## Status

- [x] Phase 0: Planning
- [x] Phase 1: Backend foundation
- [x] Phase 2: Training
- [x] Phase 3: Dataset generation
- [x] Phase 4: Compare chat
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

- [x] Four-way chat: fine-tuned model, its base model, and two hosted comparison models
- [x] Fine-tuned model served locally (mlx_lm.server; Ollama/GGUF is the long-term runtime)
- [x] Comparison models via hosted APIs

### Phase 5: Polish and deploy

- [ ] Visual theme and cohesive layout
- [ ] Accessibility pass (WCAG AA)
- [ ] Link-based navigation
- [ ] Deploy the web shell online (training stays local, Apple Silicon requirement)
- [ ] Apply theme.css (the parked design system) over the finished, working app
- [ ] Styled components built in this pass: ConfirmDialog (replaces the temporary no-confirm delete), a Thinking / VU-meter loading indicator (guitar-tuner needle, used wherever there is a wait), a nicer iters number input, cleaner status labels
- [ ] Logged-in-user display: show the current user in the nav via GET /api/auth/me, logout in a small user menu (Linear-style)
- [ ] README screenshots and the deployed-app link

### Frontend (React, TypeScript, Vite) — DONE (unstyled golden path)

- [x] Scaffold Vite plus React plus TypeScript
- [x] API client (fetch wrapper, JWT attach, 401 handling) plus a Vite dev proxy
- [x] App shell: React Router, nav, protected routes
- [x] Auth: login and signup, real token round-trip
- [x] Datasets: full CRUD in the UI (create, read, edit pre-filled, delete)
- [x] Dataset detail: browse and edit QA pairs, edit the use-case prompt, generate pairs, import from a preset
- [x] Train: config form, start a run, live status polling
- [x] Models: read-only list of fused models
- [x] Compare: four-column screen, lazy session, model picker, fan-out replies, multi-turn transcript
- [x] Backend addition: read-only fine-tuned-models endpoint (list plus get), needed for Models and Compare
- [ ] Styling pass: apply the theme over the finished app (see Phase 5 and Brand and design)

### Presentation and demo prep (before Tuesday)

- [ ] Pre-stage demo data and tokens for a flawless live run
- [ ] Generate a geography dataset and fine-tune on it, to demo the fine-tuned vs untuned divergence live (la Ville Rose / Dominican Republic capital)
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

### Generation and dataset UX

- [ ] Auto-fill the use-case prompt from the dataset name and description: when the prompt is empty, pre-populate the generation prompt editor with a draft built from the dataset's name and description, so a well-described dataset is ready to generate from with little or no typing (the description often already reads as a usable prompt). Editable and non-destructive before saving

### Compare chat depth

Enhancements to the test-agent chat, captured post-MVP.

- [x] Multi-turn conversation: each column threads its own history (shared user turns plus only its own replies) so the compare is a real chat, not one-shot prompts. DONE; context-window management is the remaining refinement.
- [ ] Surface per-column errors in the response and UI instead of silently skipping a failed column (needs an error or status field on chat_messages)
- [ ] Per-session model choice surfaced in the UI (compare_model_a and compare_model_b are already stored on the session)
- [ ] Parallelize the fan-out: call the four backends concurrently instead of sequentially, to cut response latency

### Training error explainer

When a training or fuse run fails, feed the backend log to an LLM and return a plain-language
explanation of what went wrong and how to fix it, shown in the UI instead of a raw traceback. Fits
the product's whole thesis: it abstracts something brutally technical, so it should explain failures,
not dump them. New backend endpoint plus an LLM call plus UI. A post-MVP differentiator.

### Sharing and visibility

- [ ] Owner can mark a dataset public or private (is_public flag on datasets)
- [ ] Owner can mark a fine-tuned model public or private (is_public flag on fine_tuned_models)
- [ ] Read and list queries include public items from other users; writes stay owner-only
- [ ] Authorization rule: read if owner OR public; create, update, delete if owner only
- [ ] Supports the open-source, shareable spirit of the project