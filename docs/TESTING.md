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

(to be added)

## QA pairs

(to be added)

## Training runs

(to be added)

## Fine-tuned models

(to be added)

## Chat sessions and messages

(to be added)