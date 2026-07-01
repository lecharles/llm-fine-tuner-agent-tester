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

(to be added)

## Fine-tuned models

(to be added)

## Chat sessions and messages

(to be added)