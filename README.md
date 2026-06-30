# LLM Fine Tuner & Agent Tester

Fine-tune a small open-weights LLM as easily as tuning a guitar, then test it side by side against other models. Local-first, built for Apple Silicon.

## What it is

This app takes the hard parts of fine-tuning a language model and hides them behind a simple UI. Pick a small model, build or generate a question-answer dataset for your use case, train a QLoRA adapter on your own Mac, export the result, and compare its answers against two other models in a three-way chat.

It is a deliberately simplified take on the local fine-tuning workflow: one model family, one method, one dataset format, done well.

## Core features (MVP)

- Account sign up and sign in, with per-user ownership of all data.
- Model selection: Llama 3.2 1B by default, 3B optional. Pulled and run locally.
- Dataset builder: question-answer pairs, either imported from Hugging Face or generated from a plain-English description of your business or use case.
- Training: QLoRA on Apple Silicon via MLX, with a configurable number of epochs.
- Export: fuse the adapter and save to GGUF for local runners.
- Three-way compare chat: your fine-tuned model next to two other models.

## Tech stack

- Frontend: React, TypeScript, Vite
- Backend: FastAPI, Python
- Auth: JWT
- Fine-tuning: MLX and mlx-lm
- Local model runtime: Ollama and GGUF

## Planning materials

- [User stories](docs/USER_STORIES.md)
- [Entity relationship diagram](docs/ERD.md)
- [Wireframes](docs/WIREFRAMES.md)

## Roadmap

- React Native build for iOS and Android from the same core.
- Native macOS app.
- Additional small model families beyond Llama.
- In-app guides that explain fine-tuning, dataset design, hyperparameters, export, and testing.

## About

A home-lab project built to go deep on React, TypeScript, and FastAPI, and to serve as a portfolio piece for product engineering work on AI developer tooling.