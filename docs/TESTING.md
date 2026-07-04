# Testing

Running log of curl commands used to test the API, organized by resource. 
Pretty-print JSON responses by piping to jq. Living API documentation and a re-runnable smoke test.

Base URL for local development: http://localhost:8000

Convention: capture the JWT from login into a shell variable, then reuse it on protected routes. 
The token is sensitive, do not paste it into shared docs or screenshots.

## Health

    curl -s http://localhost:8000/health | jq

Expected: {"status": "ok"}

## Auth

Sign up:

    curl -s -X POST http://localhost:8000/api/auth/signup \
      -H "Content-Type: application/json" \
      -d '{"email": "carlos@example.com", "password": "testpass123", "display_name": "Carlos"}' | jq

Expected: 201, the new user (id, email, display_name, created_at), no password field. A duplicate email returns 400 "Email already registered".

Log in and capture the token:

    TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
      -d "username=carlos@example.com&password=testpass123" | jq -r .access_token)

Note: login uses form fields (username, password), not JSON.

Current user, a protected route that proves the guard:

    curl -s http://localhost:8000/api/auth/me -H "Authorization: Bearer $TOKEN" | jq

Without the token the same route returns 401. With it, returns the logged-in user.

## Datasets

Create (owner set from token, not body):

    curl -s -X POST http://localhost:8000/api/datasets -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name": "Support FAQ", "description": "Customer support Q&A", "source": "generated", "use_case_prompt": "A SaaS billing support assistant"}' | jq

List (only your own):

    curl -s http://localhost:8000/api/datasets -H "Authorization: Bearer $TOKEN" | jq

Read one:

    curl -s http://localhost:8000/api/datasets/1 -H "Authorization: Bearer $TOKEN" | jq

Update (partial, exclude_unset):

    curl -s -X PUT http://localhost:8000/api/datasets/1 -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name": "Support FAQ (v2)"}' | jq

Delete:

    curl -s -X DELETE http://localhost:8000/api/datasets/1 -H "Authorization: Bearer $TOKEN" -w "%{http_code}"

Ownership isolation (create a second user, log in as them, confirm they cannot see or touch yours):

    TOKEN2=$(curl -s -X POST http://localhost:8000/api/auth/login -d "username=intruder@example.com&password=testpass123" | jq -r .access_token)
    curl -s http://localhost:8000/api/datasets -H "Authorization: Bearer $TOKEN2" | jq
    curl -s http://localhost:8000/api/datasets/1 -H "Authorization: Bearer $TOKEN2" | jq

Expected for the intruder: empty list, then 404 "Dataset not found" (a 404, not a 403, so the API does not even confirm the resource exists to a non-owner).

## QA pairs

Nested under a dataset. Ownership flows through the parent dataset.

Create a pair in dataset 1:

    curl -s -X POST http://localhost:8000/api/datasets/1/qa-pairs -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"question": "How do I update my billing address?", "answer": "Go to Settings, then Billing, and edit the address field."}' | jq

List pairs in dataset 1:

    curl -s http://localhost:8000/api/datasets/1/qa-pairs -H "Authorization: Bearer $TOKEN" | jq

Update a pair (partial):

    curl -s -X PUT http://localhost:8000/api/datasets/1/qa-pairs/1 -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"answer": "Go to Settings > Billing > Address to update it."}' | jq

Nested ownership isolation (intruder blocked at the dataset check, before reaching pairs):

    curl -s http://localhost:8000/api/datasets/1/qa-pairs -H "Authorization: Bearer $TOKEN2" | jq

Expected: 404 "Dataset not found" (note: "Dataset not found", not "QA pair not found", the guard fires at the parent level).

## Debugging notes

- An empty auth variable (e.g. forgetting to set TOKEN2) sends "Bearer " with no token and produces a 500, not a 401. The tell is a jq "invalid numeric literal" error, which means the response was HTML (an error page), not JSON. When jq complains about invalid literals, look at the raw response first.
- Verify a token variable is set with: echo ${#TOKEN2} (prints length, not the token). A big number is good; 0 or 4 means it is empty or "null".


## Training runs

Drives the fine-tuning pipeline: convert QA pairs to JSONL, train via mlx-lm, fuse the adapter onto the bf16 base. Assumes $TOKEN is set (see Auth) and mlx-lm is installed (pipenv install "mlx-lm[train]"). Training requires Apple Silicon. Commands run from the backend/ folder.

Create a dataset for the run and capture its id:

    DATASET_ID=$(curl -s -X POST http://localhost:8000/api/datasets -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name": "Fine-tune smoke test", "source": "manual", "use_case_prompt": "A terse assistant that answers in one sentence"}' | jq -r .id)

Seed a handful of QA pairs (training needs at least a batch worth; the batch size is 4):

    for p in \
      '{"question":"What is the capital of France?","answer":"Paris."}' \
      '{"question":"How many continents are there?","answer":"Seven."}' \
      '{"question":"What language is spoken in Brazil?","answer":"Portuguese."}' \
      '{"question":"Who wrote Romeo and Juliet?","answer":"William Shakespeare."}' \
      '{"question":"What is the largest planet in our solar system?","answer":"Jupiter."}' \
      '{"question":"What is the boiling point of water in Celsius?","answer":"One hundred degrees."}'; do
      curl -s -X POST "http://localhost:8000/api/datasets/$DATASET_ID/qa-pairs" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "$p" > /dev/null
    done

Start a training run with a small iters for a fast pass, capture its id:

    RUN_ID=$(curl -s -X POST http://localhost:8000/api/training-runs -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"dataset_id\": $DATASET_ID, \"iters\": 50}" | jq -r .id)

Expected: 201, a run with status "queued". A dataset with no pairs returns 400; a dataset that is not yours returns 404.

Poll status (re-run until it settles); the first run is slow because it downloads models:

    curl -s http://localhost:8000/api/training-runs/$RUN_ID -H "Authorization: Bearer $TOKEN" | jq

Expected: status moves queued -> running -> completed, with completed_at set at the end.

List your runs (newest first):

    curl -s http://localhost:8000/api/training-runs -H "Authorization: Bearer $TOKEN" | jq

Confirm the fused model is on disk:

    ls -lh _training_runs/$RUN_ID/fused_model/

Expected: model.safetensors plus config and tokenizer files. The run workspace also holds data/ (the JSONL), adapters/ (the trained adapter), and train.log.

If a run fails, read the logs (training first, then fuse):

    cat _training_runs/$RUN_ID/train.log

    cat _training_runs/$RUN_ID/fused_model/fuse.log

## Disk and cleanup

Fine-tuning artifacts are large and local (gitignored under _training_runs/). Handy for watching disk and resetting before a demo. Run from the backend/ folder.

See per-run sizes plus the shared model cache:

    du -sh _training_runs/* ~/.cache/huggingface/hub

Delete one run's artifacts (reclaims about 2.3GB; keep the run you want for the demo):

    rm -rf _training_runs/<run_id>

Reset all runs before a fresh demo (keeps the model cache, so no re-download):

    rm -rf _training_runs/*

## Generation and import

Two ways to fill a dataset with QA pairs: generate from a use-case description (LLM, billed) or
import from a Hugging Face preset (free, network). Both are owner-checked and append to the dataset.
Assumes $TOKEN is set (see Auth) and ANTHROPIC_API_KEY is in backend/.env for generation.

Generate pairs from the dataset's use_case_prompt (a few cents, a few seconds):

    curl -s -X POST http://localhost:8000/api/datasets/3/generate -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"count": 5}' | jq

Expected: 201 and an array of new pairs. A dataset with no use_case_prompt returns 400; a provider
failure returns 502.

Import pairs from a preset (free; the first import of a preset downloads and caches it):

    curl -s -X POST http://localhost:8000/api/datasets/3/import -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"preset": "general", "count": 10}' | jq

Expected: 201 and an array of pairs from the dataset. An unknown preset returns 400 with the valid
list; a load failure or zero mapped pairs returns 502. Presets so far: general (Dolly), finance.

Swagger: both live in the generation group as POST /api/datasets/{dataset_id}/generate and /import.
Authorize first (the padlock must show locked), put the dataset id in the path box, body as above.
A 401 "Not authenticated" means the Swagger token expired; re-Authorize.

## Fine-tuned models

(to be added)

## Chat sessions and messages

(to be added)