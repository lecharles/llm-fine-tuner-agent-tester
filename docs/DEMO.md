# G1 Demo Run-Through v2 — full current loop (S14 refresh)

**Gate:** the whole product loop end to end. v2 extends the v1 script (S4)
with everything shipped since: `/welcome`, CSV/JSONL import (S12), live loss
curve (S11), surfaced training failures (H3), compare model pickers + the
optional Ollama column (S13), the ~150-word answer cap (H4), and a VPS
variant. Budget: **10–20 iters** for the demo, **200–400** for a real tune
(see `docs/QUICKSTART.md`).

## Variants

- **A. Mac (full)** — generate → import → train → export → compare, local engines only.
- **B. VPS (partial)** — http://76.13.122.86:8090 — welcome → generate → import → compare; training must refuse with 425. ~5 min.

## Prereqs (both)

- Repo pulled to current `main`; server up (`llmtuner up` on Mac; keepalive runs :8090 on the VPS).
- Mac: Ollama running, MLX installed. No `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` needed — the ladder must fall through to local Ollama; that is the point.
- A scratch CSV handy: `demo-refunds.csv` with a header `question,answer` and 3 rows (any refund-policy Q&A; no real customer data).

## Script A — Mac (~20 min)

### 1. Welcome + account (2 min)
1. Open http://localhost:8000 — `/` must redirect to **/welcome**; sidebar's first entry is Welcome.
2. Sign up / sign in. **Expect:** your new account owns everything below; a second account sees none of it.

### 2. Generate (3 min)
1. **Datasets → New dataset**, name `g1-demo-<initials>`.
2. Prompt: *"10 Q&A pairs about our refund policy: 30-day window, receipt required."*
3. Iters: **10** (smoke budget). Generate.
4. **Expect:** 10 pairs with local-Ollama source badges; no hang (ladder messages are visible).

### 3. Import (2 min) — new in v2
1. Same dataset → **Import from file** → pick `demo-refunds.csv`.
2. **Expect:** the 3 pairs append immediately with `csv` source; a bad file (e.g. no `question` column) shows the 400 reason inline, and the existing pairs are untouched.

### 4. Train with live curve (8 min)
1. **Train**, pick `g1-demo-*`, iters **10–20**, start.
2. **Expect (S11):** the loss curve appears on the run card and gains a point every poll tick while status is `running`.
3. Failure behavior (H3): if the run dies, the card shows a **red error box** with the exception text + log tail — never silent. (`scripts/collect-run-logs.sh` gathers logs for the issue.)
4. On completion the model appears under **Models** as `g1-demo-*-qlora`; fuse/export yields GGUF.

### 5. Compare (5 min) — extended in v2
1. **Compare**: col A = base model, col B = `g1-demo-*-qlora`.
2. Open the **OpenAI column's model dropdown** and pick `gpt-4o` (or `gpt-5.5`); same for Anthropic → `claude-sonnet-5`. (Skip if no keys — they then error in-column, which is itself a check.)
3. **Add an Ollama column** from the installed-model list (`llama3.2:1b`) — five columns.
4. Ask: *"Can I return this without a receipt after 40 days?"*
5. **Expect:** tuned column cites 30-day + receipt; base is generic; every answer ≈ ≤150 words (H4 cap); failed columns show their reason in-column.

## Script B — VPS (~5 min)

1. Open http://76.13.122.86:8090 → login (hard refresh first; H1 regression check).
2. **/welcome** renders; create a dataset, generate 10 pairs — **Expect:** generation falls through to the server's Ollama, badges visible.
3. Import the same `demo-refunds.csv` — **Expect:** appends fine on the shared instance.
4. Try to start training — **Expect:** **425 "training runs on the Mac app only"**, no doomed run created (H3 preflight).
5. Compare: no fine-tuned model here, so compare base vs the Ollama column vs any configured hosted columns. **Expect:** 150-word cap applies, in-column errors persist (H3).

## Pass criteria

- [ ] A: all five steps complete with local engines only.
- [ ] A: loss curve visibly updates during `running`; any failure shows the red box.
- [ ] A: CSV import appends pairs; bad file gives a readable 400 with no data loss.
- [ ] A: tuned answer beats base on the refund question; all answers ≈ capped.
- [ ] B: login 200, generate ok, import ok, train 425, compare ok.
- [ ] Total wall time: A < 30 min, B < 10 min.

## If it fails

- Generation stalls → `ollama list`, then the ladder message text.
- Training 425 **on the Mac** → MLX missing; `llmtuner doctor`.
- Training silent → H3 regression; `scripts/collect-run-logs.sh`, file an issue.
- Ollama column list empty → Ollama down or `OLLAMA_BASE_URL` unset (S13); fix the service, not the UI.
- Compare empty column → read the in-column reason; verify engine auto-start.
- VPS login 401 → stale :8090 process (H1); `scripts/keepalive.sh status`, restart from HEAD.

Record run date + result in the commit body `Verification:` line; v1's G1
sign-off lives in the S4 commit (a9dc265).
