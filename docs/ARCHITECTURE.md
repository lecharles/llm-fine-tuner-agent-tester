# Architecture

How the LLM Fine Tuner & Agent Tester fits together: the system layout and the flow of data between pieces. 
Built up as the system takes shape.

## System overview

High-level components and how they connect. (Refined as the backend and frontend come online.)

````mermaid
flowchart LR
    User[User in browser] --> FE[React + TypeScript frontend]
    FE --> API[FastAPI backend]
    API --> DB[(PostgreSQL)]
    API --> MLX[mlx-lm training on Apple Silicon]
    API --> Ollama[Ollama local model runtime]
    API --> Hosted[Hosted LLM APIs for comparison and generation]
````

## Backend layers

Request flow through the backend, from route to database. (Detailed once routers and models exist.)

````mermaid
flowchart TD
    Route[API route] --> Auth[Auth dependency: verify JWT, load current user]
    Auth --> Schema[Pydantic schema: validate request]
    Schema --> Logic[Route logic + ownership check]
    Logic --> ORM[SQLAlchemy models]
    ORM --> DB[(PostgreSQL)]
````

## Training pipeline

How a dataset becomes a fine-tuned model. (Sequence diagram added when we build Phase 2.)

````mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant Job as Background job
    participant MLX as mlx-lm
    U->>API: Start training run
    API->>Job: Enqueue job, set status running
    Job->>MLX: Run QLoRA fine-tune
    MLX-->>Job: Adapter produced, fuse and export GGUF
    Job-->>API: Set status completed, save model path
    U->>API: Poll status
    API-->>U: Completed
````

## Compare chat flow

How one prompt fans out to four models. (Sequence diagram added when we build Phase 4.)

````mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant FT as Fine-tuned Llama (Ollama)
    participant VB as Vanilla Llama (Ollama)
    participant OAI as OpenAI model
    participant ANT as Anthropic model
    U->>API: Send prompt
    API->>FT: Prompt
    API->>VB: Prompt
    API->>OAI: Prompt
    API->>ANT: Prompt
    FT-->>API: Reply
    VB-->>API: Reply
    OAI-->>API: Reply
    ANT-->>API: Reply
    API-->>U: Four replies, persisted
````

## Data model

See [ERD.md](ERD.md) for the full entity diagram and relationships.
````
````