# Research Spike: mlx-lm Training Pipeline

Findings for Phase 2, the training hero feature. This spike answers how to drive mlx-lm
fine-tuning from our FastAPI backend, before any code is written. Scope is deliberately
narrow: the five questions below plus the one link in the chain that is genuinely risky.

Date: July 1, 2026. Target machine: MacBook Pro M5, 16GB, macOS. Default model:
Llama 3.2 1B Instruct, 4-bit (`mlx-community/Llama-3.2-1B-Instruct-4bit`).

## Verdict

1. Invoke training with the `mlx_lm.lora` command as a subprocess from the background
   job. It is the stable, documented surface. The lower level Python tuner API exists but
   is not worth the coupling for our needs.
2. Training data is JSONL, one example per line. Our QA pairs map cleanly to either the
   `completions` format or the `chat` format. Recommend `chat`, because it matches how the
   model is prompted at inference in the compare-chat and it applies the model's chat template.
3. A 1B 4-bit QLoRA run on roughly 100 pairs should finish in single digit minutes with
   peak memory well under 4GB, comfortably inside 16GB. Training length is controlled by
   `--iters`, so we can dial it for a fast, reliable demo. Exact numbers must be measured
   on-device.
4. Export is fuse then convert to GGUF, which confirms the hypothesis in shape. The catch:
   going to GGUF directly from a 4-bit base is a known pain point. The robust path is to
   fuse the adapter onto the non-quantized base, then convert. This is the one thing to
   validate end to end before building orchestration.
5. Serving has two OpenAI-compatible options. Primary: GGUF plus Ollama, which matches our
   `fine_tuned_models.gguf_path` design and the Ollama runtime already on the machine.
   Fallback: `mlx_lm.server`, which serves the MLX model directly with no conversion. Both
   speak `/v1/chat/completions`, which is convenient for Phase 4.

Do this first in Phase 2: run the full train, fuse, GGUF, Ollama chain by hand with the 1B
model and confirm it produces a working model file. If that link is broken on the installed
version, we want to know on day one, not after building the job runner around it.

## Sources

- mlx-lm LoRA/QLoRA docs (authoritative): https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md
- mlx-lm server docs (authoritative): https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md
- mlx-lm package overview: https://pypi.org/project/mlx-lm/
- Default 1B model card: https://huggingface.co/mlx-community/Llama-3.2-1B-Instruct-4bit
- Non-quantized base for fusing: https://huggingface.co/mlx-community/Llama-3.2-1B-Instruct-bf16
- Ollama model import docs: https://docs.ollama.com/import
- QLoRA to GGUF friction, our exact model: https://github.com/ml-explore/mlx-lm/issues/353
- Working train, fuse, convert, Ollama flow: https://github.com/ml-explore/mlx-examples/issues/1382
- Recent fuse dequantize bug: https://github.com/ml-explore/mlx-lm/issues/659

## 1. Invoking training: CLI subprocess vs Python API

There are two ways in.

The CLI. Install with `pip install "mlx-lm[train]"` (for us, `pipenv install "mlx-lm[train]"`).
The entry point is `mlx_lm.lora`. A minimal run:

```
mlx_lm.lora \
    --model mlx-community/Llama-3.2-1B-Instruct-4bit \
    --train \
    --data ./data \
    --iters 300
```

`--data` is a directory, not a file. The loader expects `train.jsonl` inside it, an optional
`valid.jsonl` for validation loss, and `test.jsonl` when running with `--test`. Adapter
weights are written to `adapters/` by default, configurable with `--adapter-path`. A YAML
config can be passed with `-c/--config`, and any command-line flags override the config.

The Python API. `from mlx_lm.tuner import ...` exposes the training loop, dataset loaders,
and `TrainingArgs`. It is real, but lower level and less stable across versions, and it would
pull the training work into our web process.

Recommendation: shell out to `mlx_lm.lora` as a subprocess from the background job. Reasons:

- It is the documented, stable interface. The Python tuner API is a moving target.
- A subprocess is naturally cancellable and isolatable. If training crashes or runs the
  machine out of memory, it takes down a child process, not our FastAPI worker.
- We already treat status as a lifecycle in `training_runs`. Launch the subprocess, flip
  status to running, watch the process, then flip to completed or failed on exit code. The
  JS analogue is `child_process.spawn` with an exit handler, not calling a library in-process.

Note on QLoRA. QLoRA is not a separate fine-tune type. Passing a quantized (4-bit) model
makes LoRA train as QLoRA automatically. The docs state this directly: if `--model` points
to a quantized model the training uses QLoRA, otherwise regular LoRA. So `--fine-tune-type`
takes `lora` (default), `dora`, or `full`, and there is no `qlora` value to pass. Our
`training_runs.method` field defaults to `"qlora"`, which is fine as a human-readable label,
but the actual switch in the command is simply choosing a 4-bit `base_model`. The code must
not try to pass `--fine-tune-type qlora`.

## 2. Training data format

Local datasets are JSONL, and each example must sit on a single line. The loader auto-detects
the format from the keys present, and it ignores keys it does not recognize. Supported formats:

- `chat`: `{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}`
- `completions`: `{"prompt": "...", "completion": "..."}`
- `text`: `{"text": "..."}`
- `tools`: chat plus a `tools` array, for function-calling data. Not relevant to us.

For the `chat`, `completions`, and `tools` formats the model's Hugging Face chat template is
applied during training, so the model learns the same turn structure it will see at inference.

Our mapping. A `QAPair` has `question` and `answer`. Both formats work:

- `completions`: `{"prompt": question, "completion": answer}`. Dead simple, one to one.
- `chat`: `{"messages": [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]}`.

Recommend `chat`. The end use is a chat comparison, so training on the chat turn shape lines
up with inference, and it leaves an obvious slot for a system prompt later if we want to steer
tone. If we prefer the simpler shape, `completions` is an equally valid fallback and gets the
same chat-template treatment for a single turn.

Prompt masking. By default the loss covers every token, prompt included. Passing `--mask-prompt`
computes loss on the completion only, which for QA fine-tuning is usually what we want: teach
the model to produce the answer, not to reproduce the question. It is supported for `chat` and
`completions` data. For `chat` the final assistant message is treated as the completion.

The conversion step (task 1 of the Phase 2 build) is therefore small: read a dataset's
`qa_pairs`, write one JSON object per line to `train.jsonl` in a per-run data directory, and
optionally hold back a slice as `valid.jsonl`. This is a `.map` over the pairs plus a file write.

## 3. Time and memory for Llama 3.2 1B QLoRA

No single benchmark for exactly our setup exists, so this is an estimate anchored to nearby
data points, to be confirmed on-device.

Anchors. The mlx-lm docs benchmark Mistral 7B on an M1 Max 32GB at roughly 250 tokens per
second. A separately reported run fine-tuned Mistral 7B on 5,000 examples in about 90 minutes
on an M2 Max 32GB, with peak memory around 7GB. Our job is much smaller on both axes: the model
is roughly 7x smaller than 7B, the dataset is around 50x smaller than 5,000 examples, and the
M5 is a newer, faster chip than the M2 Max.

What that implies for us:

- Time: single digit minutes for a demo run. Training length is set by `--iters`, not by epochs,
  so it is a direct lever. The default is 600 iters. For roughly 100 examples we do not need
  many, and we can set `--iters` to something like 100 to 300 to guarantee the run finishes in
  a couple of minutes while still shifting behavior visibly.
- Memory: a 1B model at 4-bit is well under 1GB of weights, and a small-batch QLoRA run should
  peak comfortably under 4GB. This fits 16GB with plenty of headroom, so we should not need the
  memory escape hatches (smaller batch, fewer layers, gradient checkpointing) for the 1B. Keep
  them in mind for the optional 3B.

Important mapping note. Our `training_runs.epochs` field (default 3) does not correspond to any
mlx-lm flag directly, because mlx-lm counts iterations, not epochs. One iteration processes one
batch. If we want to keep exposing epochs in the UI, convert on the way into the command:
`iters = epochs * ceil(num_examples / batch_size)`. Alternatively, drive `--iters` directly and
treat epochs as derived. This is a small decision to make when we build the start-training endpoint.

## 4. Export: fuse then GGUF, the risky link

Fusing. `mlx_lm.fuse` merges the learned adapter back into the base model. By default it loads
adapters from `adapters/` and writes the merged model to `fused_model/`. It can optionally push
to the Hugging Face Hub and can export straight to GGUF.

```
mlx_lm.fuse --model <base> --adapter-path adapters
```

The GGUF catch. The docs say the built-in GGUF export supports only Mistral, Mixtral, and
Llama style models, in fp16 precision. Llama 3.2 qualifies on the family. The real friction is
the quantized base. Fusing an adapter that was trained on a 4-bit model and then serializing to
GGUF hits tensor-mapping and dtype errors in practice. Reported failure modes across upstream
issues include a `U32` dtype key error, a "can only serialize row-major arrays" error on newer
mlx-lm, missing-tensor errors when loading the result, and, most recently, a bug where
`mlx_lm.fuse --dequantize` raises a `NameError` and, after patching, the fused model fails to
load. One of those reports is our exact case: QLoRA on Llama 3.2 1B Instruct 4-bit, fuse,
convert to GGUF.

The workaround that people report working: do not fuse onto the 4-bit base. Fuse the adapter
onto the non-quantized base (`mlx-community/Llama-3.2-1B-Instruct-bf16`) instead. The adapter is
just low-rank deltas of the same shapes, so it applies to the fp16 weights, and fp16 to GGUF is
the clean, supported path. There is a minor fidelity caveat, since the adapter was trained
against the slightly different quantized weights, but in practice this produces a usable model
and sidesteps the quantized-tensor errors entirely.

Recommended export path, in order of preference:

Path A, robust. Fuse onto the fp16 base, then convert with llama.cpp:

```
mlx_lm.fuse \
    --model mlx-community/Llama-3.2-1B-Instruct-bf16 \
    --adapter-path adapters \
    --save-path fused_model
```

```
python convert_hf_to_gguf.py fused_model --outfile model-f16.gguf --outtype f16
```

Path B, shortcut to try first. The one-command built-in export:

```
mlx_lm.fuse \
    --model mlx-community/Llama-3.2-1B-Instruct-bf16 \
    --adapter-path adapters \
    --export-gguf
```

This writes `fused_model/ggml-model-f16.gguf`. If it works on the installed version, it is the
least effort. If it errors, fall back to Path A.

Either way we end with a GGUF file, which is exactly what `fine_tuned_models.gguf_path` is for.
Size for a 1B fp16 GGUF is roughly 2.5GB, which is fine locally. If we want it smaller we can
quantize during the Ollama import (below), and record whichever we ship in `size_mb`.

Why fuse at all instead of shipping the bare adapter to Ollama: Ollama can import a GGUF adapter,
but it wants a non-quantized adapter matched to the exact base, and quantization schemes differ
between frameworks. Fusing into a full model first and shipping one self-contained GGUF avoids
that whole class of mismatch.

## 5. Serving the fine-tuned model locally

Two OpenAI-compatible options, both useful.

Ollama, the primary path. After producing the GGUF, import it with a Modelfile:

```
FROM ./model-f16.gguf
```

```
ollama create ft-<run-id> -f Modelfile
```

Ollama can also quantize an fp16 GGUF during creation with `--quantize q4_K_M`, which shrinks a
1B model to well under 1GB. The imported model is then available on Ollama's local REST API on
port 11434, including an OpenAI-compatible `/v1/chat/completions` endpoint. This matches our
architecture (Ollama as the local runtime) and the fact that a quantized Llama is already
running in Ollama on this machine.

`mlx_lm.server`, the fallback path. mlx-lm ships its own lightweight HTTP server that mimics the
OpenAI chat API on port 8080 by default:

```
mlx_lm.server --model fused_model --port 8080
```

It can also serve a base model plus an adapter path without fusing at all, which is the fastest
possible route to a working reply. The docs note it only implements basic security checks and is
not for production, which is fine for a local demo. This is the escape hatch if GGUF export
fights us: we can still demo a working fine-tuned model over an OpenAI-shaped API with zero
conversion.

Phase 4 convenience. Ollama, `mlx_lm.server`, and the hosted comparison models all speak the
same OpenAI chat-completions shape. That means the compare-chat can talk to all three models
through one client shape, varying only the base URL and model name. This de-risks Phase 4 and is
a clean talking point for the presentation.

## Hypotheses checked

All five starting hypotheses hold. One carries an important caveat.

- CLI is `mlx_lm.lora --train --data <dir> --iters N`: confirmed. `--model` is also required,
  and `--data` is a directory containing `train.jsonl`.
- A 4-bit model makes LoRA become QLoRA automatically: confirmed, stated verbatim in the docs.
  There is no `qlora` fine-tune type to pass.
- Data is JSONL, chat messages or prompt/completion: confirmed. Also supports `text` and `tools`.
  One example per line.
- Export is fuse then convert to GGUF: confirmed in shape, with the caveat that GGUF from a
  quantized base is finicky. Fuse onto the fp16 base to get a clean conversion.
- mlx-lm exposes an OpenAI-compatible endpoint via `mlx_lm.server`: confirmed. It serves
  `/v1/chat/completions` and can take an `adapters` path.

## Recommended Phase 2 pipeline

Mapped to the existing task list and data model.

1. Convert QA pairs to JSONL. Read a dataset's `qa_pairs`, write `chat` format to
   `train.jsonl` in a per-run data directory. Optionally hold back a `valid.jsonl` slice.
2. Run training as a background job. Spawn `mlx_lm.lora --model <4-bit base> --train
   --data <dir> --iters <n> --adapter-path <run-dir>/adapters`, with `--mask-prompt`. Move
   `training_runs.status` queued to running on spawn, and to completed or failed on exit. Carry
   `base_model` and `learning_rate` from the row into flags. Map `epochs` to `--iters` if we
   keep the epochs field.
3. Fuse and export GGUF. On success, fuse the adapter onto the fp16 base and produce a GGUF
   (Path A, with Path B as a shortcut). Create a `fine_tuned_models` row with `gguf_path`,
   `format = "gguf"`, `size_mb`, and `status`.
4. Endpoints. One to start a training run, one to poll its status. Ownership enforced the same
   way as the CRUD routes, owner set from the JWT, reads filtered by owner.

Serving (Ollama import) belongs to Phase 4, but validate it now as part of the chain check.

## On-device validation checklist

Run these by hand once, in order, before writing any Phase 2 code. Each is a go or no-go.

- [ ] `pipenv install "mlx-lm[train]"` succeeds, and pin the working version in the Pipfile.
- [ ] Hand-write a tiny `train.jsonl` (10 to 20 chat examples) and run `mlx_lm.lora` on the
      1B 4-bit base for around 100 iters. Confirm it completes and note wall-clock time and peak memory.
- [ ] `mlx_lm.generate` with the base plus `--adapter-path` shows the fine-tune changed behavior.
- [ ] Fuse onto the bf16 base and produce a GGUF (try Path B, fall back to Path A). Confirm a
      GGUF file lands on disk.
- [ ] `ollama create` from that GGUF, then a test prompt returns a coherent reply.
- [ ] Record the versions and the exact working commands in CONVENTIONS and the log.

## Open risks and decisions

- GGUF export is the top risk. Mitigated by fusing onto the fp16 base, with `mlx_lm.server` as
  a demo-safe fallback if conversion still fails. Resolve this first.
- Version drift. Several of the export bugs above are version-specific, some fixed and some open.
  Pin a known-good mlx-lm and llama.cpp once the chain works, and do not upgrade mid-week.
- iters, not epochs (reversed). The training knob is iters, matching mlx-lm's native unit.
  Simpler and less code, no conversion. training_runs.epochs was renamed to iters.
- Model download size and first-run latency. The base model downloads from Hugging Face on first
  use and is then cached. Pre-pull it before the demo so nothing fetches on stage.
