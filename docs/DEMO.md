# G1 Demo Run-Through — local-engines end-to-end (S4 gate)

**Gate:** generate → train → compare on the Mac with **only local engines**
(no cloud credits). Run before the desktop slices (D3+). Uses the smoke
iteration budget: **10–20 iters** for the demo, 200–400 for a real tune
(see `docs/QUICKSTART.md`).

## Prereqs

- Mac with Apple Silicon, repo pulled, `llmtuner up` serving + browser open.
- Local engines: Ollama running (generation fallback), MLX installed (training).
- No `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` needed — the ladder must fall
  through to local Ollama; that is the point of this demo.

## Script (~15 min)

### 1. Generate (3 min)
1. Open **Datasets → New dataset**, name it `g1-demo-<your-initials>`.
2. Prompt: *"10 Q&A pairs about our refund policy: 30-day window, receipt required."*
3. Iters: **10** (smoke budget). Generate.
4. **Expect:** 10 pairs appear; each shows its source engine badge (local Ollama).

### 2. Train (8 min)
1. Open **Train**, pick dataset `g1-demo-*`, iters **10–20**, start run.
2. Watch the run status — it must progress, never sit silent (H3: failures
   surface with error text + log tail).
3. **Expect:** run completes; model appears under **Models** as
   `g1-demo-*-qlora`.

### 3. Compare (4 min)
1. Open **Compare**: column A = base model, column B = `g1-demo-*-qlora`.
2. Ask: *"Can I return this without a receipt after 40 days?"*
3. **Expect:** tuned column cites 30-day + receipt; base column is generic.
   Failed columns show their reason in-column (H3).

## Pass criteria

- [ ] All three steps complete with local engines only.
- [ ] No silent failures (every error visible in UI).
- [ ] Tuned answer beats base answer on the refund question.
- [ ] Total wall time < 20 min at smoke iters.

## If it fails

- Generation stalls → check Ollama (`ollama list`), then ladder message text.
- Training 425 "Mac app only" → you are on the VPS build; G1 needs the Mac.
- Training silent → H3 regression; capture `fuse.log` via
  `scripts/collect-run-logs.sh` and file an issue.
- Compare empty column → read the in-column reason; verify engine auto-start.

Record the run date + result in the S4 commit body (`Verification:` line).
