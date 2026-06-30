# Wireframes

Bare-bones wireframes for the main pages of the LLM Fine Tuner & Agent Tester app. Layout and structure only, no color or styling. These guide the build; visual design comes later.

Every signed-in page shares a left sidebar: Dashboard, Datasets, Train, Models, Chat, with the account and log out pinned at the bottom.

## 1. Landing and auth

```
+------------------------------------------------+
|                                                |
|         LLM Fine Tuner & Agent Tester          |
|         Fine-tune an LLM as easily as          |
|         tuning a guitar.                        |
|                                                |
|      +--------------------------------------+  |
|      |   [ Log in ]      [ Sign up ]        |  |
|      |                                      |  |
|      |   Email     [___________________]    |  |
|      |   Password  [___________________]    |  |
|      |                                      |  |
|      |            [ Continue ]              |  |
|      +--------------------------------------+  |
|                                                |
+------------------------------------------------+
```

## 2. Dashboard

```
+----------------+----------------------------------+
| LLM Tuner      |  Dashboard                       |
|                |                                  |
| > Dashboard    |  +----------------------------+  |
|   Datasets     |  |  + New dataset             |  |
|   Train        |  +----------------------------+  |
|   Models       |  +----------------------------+  |
|   Chat         |  |  + Start a training run    |  |
|                |  +----------------------------+  |
|                |                                  |
| [user]         |  Recent activity                 |
| [ Log out ]    |  - Dataset: support-faq          |
|                |  - Run: #12  (completed)         |
|                |  - Model: faq-1b  (ready)        |
+----------------+----------------------------------+
```

## 3. Datasets

```
+----------------+----------------------------------+
| LLM Tuner      |  Datasets            [ + New ]   |
|                |                                  |
|   Dashboard    |  +----------------------------+  |
| > Datasets     |  | Name      | Source | Pairs |  |
|   Train        |  | support   | gen    | 100   |  |
|   Models       |  | legal-qa  | hf     | 50    |  |
|   Chat         |  | notes     | manual | 12    |  |
|                |  +----------------------------+  |
| [user]         |  Click a row to open a dataset   |
| [ Log out ]    |                                  |
+----------------+----------------------------------+
```

## 4. Dataset detail

```
+----------------+----------------------------------+
| LLM Tuner      |  support-faq      [ Edit ][ Del ]|
|                |  Source: generated               |
|   Dashboard    |                                  |
| > Datasets     |  Generate Q&A pairs              |
|   Train        |  +----------------------------+  |
|   Models       |  | Describe your use case     |  |
|   Chat         |  | [________________________] |  |
|                |  | Count [ 100 ]  [ Generate ]|  |
| [user]         |  +----------------------------+  |
| [ Log out ]    |                                  |
|                |  Q&A pairs           [ + Add ]   |
|                |  +----------------------------+  |
|                |  | Question | Answer  | edit  |  |
|                |  | ...      | ...     | del   |  |
|                |  +----------------------------+  |
+----------------+----------------------------------+
```

## 5. Train

```
+----------------+----------------------------------+
| LLM Tuner      |  Train                           |
|                |                                  |
|   Dashboard    |  Base model                      |
|   Datasets     |  ( ) Llama 3.2 1B   ( ) 3B       |
| > Train        |                                  |
|   Models       |  Method    [ QLoRA        v ]    |
|   Chat         |  Dataset   [ select...    v ]    |
|                |  Epochs    [ 3 ]                 |
| [user]         |                                  |
| [ Log out ]    |         [ Start training ]       |
|                |                                  |
|                |  Status: queued > running >      |
|                |          completed               |
+----------------+----------------------------------+
```

## 6. Models

```
+----------------+----------------------------------+
| LLM Tuner      |  Fine-tuned models               |
|                |                                  |
|   Dashboard    |  +----------------------------+  |
|   Datasets     |  | Name     | Base | Status   |  |
|   Train        |  | faq-1b   | 1B   | ready    |  |
| > Models       |  | legal-3b | 3B   | exported |  |
|   Chat         |  +----------------------------+  |
|                |                                  |
| [user]         |  Per model:                      |
| [ Log out ]    |  [ Export GGUF ] [ Chat ] [ Del ]|
+----------------+----------------------------------+
```

## 7. Compare chat

```
+----------------+----------------------------------+
| LLM Tuner      |  Compare chat                    |
|                |  Mine: faq-1b                    |
|   Dashboard    |  vs [ compare A v ] [ compare B v]|
|   Datasets     |                                  |
|   Train        |  +--------+--------+----------+  |
|   Models       |  | Mine   | A      | B        |  |
| > Chat         |  |        |        |          |  |
|                |  | resp   | resp   | resp     |  |
| [user]         |  +--------+--------+----------+  |
| [ Log out ]    |                                  |
|                |  [ Type a prompt...     ][ Send ]|
+----------------+----------------------------------+
```