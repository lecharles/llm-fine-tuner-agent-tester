# User Stories

User stories for the LLM Fine Tuner & Agent Tester app, written as: As a [role], I want [feature], so that I can [reason].

## MVP

### Accounts

| Done | # | As a | I want to | So that I can |
|------|---|------|-----------|---------------|
|  | 1 | visitor | sign up for an account | save my datasets and models |
|  | 2 | user | log in | access my work |
|  | 3 | user | log out | keep my session secure on a shared machine |

### Datasets

| Done | # | As a | I want to | So that I can |
|------|---|------|-----------|---------------|
|  | 4 | user | create a dataset | organize training data for a use case |
|  | 5 | user | generate question-answer pairs from a plain-English description | build a dataset without writing every pair by hand |
|  | 6 | user | import a dataset from Hugging Face | start from existing data |
|  | 7 | user | view my datasets | see what I have to work with |
|  | 8 | user | view and edit the question-answer pairs in a dataset | correct or improve the data |
|  | 9 | user | rename a dataset and update its description | keep it organized |
|  | 10 | user | delete a dataset | remove ones I no longer need |

### Training

| Done | # | As a | I want to | So that I can |
|------|---|------|-----------|---------------|
|  | 11 | user | choose a base model, method, and number of iterations | control how my model is fine-tuned |
|  | 12 | user | start a training run on a chosen dataset | fine-tune a model for my use case |
|  | 13 | user | see the status of a training run | know when my model is ready |

### Models and export

| Done | # | As a | I want to | So that I can |
|------|---|------|-----------|---------------|
|  | 14 | user | view my fine-tuned models | see my results |
|  | 15 | user | export a fine-tuned model to GGUF | run it locally |
|  | 16 | user | delete a fine-tuned model | clean up old results |

### Compare chat

| Done | # | As a | I want to | So that I can |
|------|---|------|-----------|---------------|
|  | 17 | user | start a compare chat with my fine-tuned model, its base model, and two hosted models | see how fine-tuning changed the output |
|  | 18 | user | send a prompt and see all four answers side by side | compare them directly |
|  | 19 | user | revisit my past chat sessions | review earlier comparisons |

### Ownership and access

| Done | # | As a | I want to | So that I can |
|------|---|------|-----------|---------------|
|  | 20 | user | view and edit only the data I created | keep my work private |
|  | 21 | user | require guests to sign in before they can create or change data | protect my data from anonymous edits |

## Stretch goals

| Done | # | As a | I want to | So that I can |
|------|---|------|-----------|---------------|
|  | 22 | user | choose small model families beyond Llama | compare fine-tuning across architectures |
|  | 23 | user | read in-app guides on fine-tuning, dataset design, and hyperparameters | learn while I build |
|  | 24 | user | use the app on iOS and Android | manage runs from my phone |