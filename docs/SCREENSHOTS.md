# Screenshot Pass (#16, S14) — inventory, fresh captures, and re-shoot recipe

Canonical directory: `docs/screenshots/`. The legacy gallery in `screenshots/`
(storyboard from 2026-09-14) is kept linked from the README's legacy section
but is superseded by the shots below as they get captured.

## Inventory (2026-09-29 pass)

| File | Page | Captured | Source | Fresh? |
|------|------|----------|--------|--------|
| `docs/screenshots/00-login.png` | Sign in, VPS :8090 | 2026-09-29 | headless chromium, 1440×900 | ✅ fresh |
| `docs/screenshots/01-signup.png` | Sign up, VPS :8090 | 2026-09-29 | headless chromium, 1440×900 | ✅ fresh |
| `screenshots/1..6-llm-tuner.png` | Sept-14 demo storyboard | 2026-09-14 | manual | ⚠️ stale — pre-dates `/welcome` (S4), live loss curve (S11), CSV/JSONL import (S12), compare model pickers + Ollama column (S13) |

## Shot list for the full pass (issue #16 acceptance)

Capture at **1440×900**, one browser tab per shot, after logging into the VPS
team instance (public pages) or the Mac build (data-dependent pages). Use a
dataset named `demo-refunds` so shots are reproducible.

1. `00-login.png` / `1-signup.png` — done (this pass).
2. `02-welcome.png` — `/welcome` signed in: pitch card + sidebar with **Welcome** first.
3. `03-datasets.png` — `/datasets` with `demo-refunds` listed, pair counts visible.
4. `04-dataset-import.png` — dataset detail mid-*Import from file*: file picker + appended pairs with source badges (`csv`/`generated`/`ollama`).
5. `05-train-live.png` — `/train` run in `running` state with the **live loss curve** moving (S11). Needs a Mac run at 10–20 iters.
6. `06-train-error.png` — failed run row showing the red error box + log tail (H3). Repro: stop the venv mid-run or point at a poisoned dataset.
7. `07-models.png` — `/models` with a finished `demo-refunds-qlora` (fused/GGUF export state visible).
8. `08-compare.png` — `/compare` four-way: tuned vs base vs OpenAI vs Anthropic answers, all ~150 words (H4 cap).
9. `09-compare-pickers.png` — a hosted column's **model dropdown** open (S13: gpt-4o, gpt-5.5, claude-sonnet-5, …).
10. `10-compare-ollama.png` — five columns with the **ollama** column (`llama3.2:1b`) added.
11. `11-vps.jpg` — the VPS instance in a browser showing the URL bar (proof it's live at http://76.13.122.86:8090).

## Headless re-shoot recipe (VPS public pages — what the lane used)

From the VPS repo root (one-shot, no long-lived process):

```bash
timeout 60 chromium --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
  --window-size=1440,900 --virtual-time-budget=6000 \
  --screenshot=docs/screenshots/00-login.png http://127.0.0.1:8090/login
```

Sanity-check a capture actually rendered (not blank) — system `python3` has PIL:

```bash
python3 -c "from PIL import Image; im=Image.open('docs/screenshots/00-login.png').convert('RGB'); print(im.size, len(im.getcolors(2000000) or []))"
```

Expect 1440×900 and **hundreds** of distinct colors (blank white ≈ 1–3).

Authenticated pages: headless one-shot can't log in (JWT lives in the
browser session) — use the Mac browser below.

## Mac re-shoot recipe (authenticated pages 02–11)

1. `git pull` on the Mac; `llmtuner up` (or `llmtuner app`).
2. Create `demo-refunds` with 10 generated pairs + a 3-row CSV import; run 10–20 iters to have live/error/fused states to shoot.
3. Browser window exactly **1440×900**: Chrome DevTools → device toolbar → preset 1440×900, or size the floating app window with `llmtuner app --size 1440x900`.
4. macOS screenshot of the window: `Cmd+Shift+4`, then `Space`, click the window — saves `~/Desktop/<name>.png`. Rename to the shot-list filename and drop into `docs/screenshots/`.
5. `git add docs/screenshots && git commit -m 'docs: screenshot pass N' && git push`, then swap the README legacy gallery for the fresh files.

Keep secrets out of shots: confirm no `.env` text, tokens, or passwords are visible in any frame before committing.
