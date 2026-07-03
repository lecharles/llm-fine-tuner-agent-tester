# Research Spike: Phase 3 Dataset Generation

Findings for Phase 3: preset Hugging Face datasets to import, how the HF integration works, the
Q/A generation prompting strategy, and the generator model and cost. Scope mirrors the mlx spike:
answer the decisions before writing code.

Date: July 3, 2026. Prices verified against provider pages the same day; confirm before committing
a budget, model prices move.

## Verdict

1. Two-pronged Phase 3, and the two prongs cover different needs. Preset import (ready-made HF
   datasets) covers broad, well-served domains (general, medical, finance, some legal). The
   generator (describe a use case, get Q/A pairs) covers everything else, including the niche
   domains we care about (Canada tax, Dominican Republic law, US insurance), which mostly have no
   ready-made dataset. The gap is the feature: where a dataset does not exist, generation fills it.
2. Preset shortlist (all instruction/Q&A shaped, mapped to our question/answer): a general one, a
   medical one, a finance one, a legal one, and a broad instruction one. Details and licenses below.
   Pull 50-100 rows per preset for the demo (fast to train, clear behavior shift), as agreed.
3. Generation: one strong model with a fallback chain, per your call: Anthropic Fable 5 by default,
   fall back to Opus 4.8, then OpenAI. A tight system+role prompt that emits strict JSON, plus
   dedup. Roughly $0.60 per 100 pairs on Fable, and much less on the fallbacks (table below), so
   financing the demo is trivial.
4. Keys live in environment variables, never in the database. Provider SDKs (openai, anthropic).

One honest note on the default: Fable is the priciest model, had an access wobble (export-control
suspension June 12-30, restored July 1), and needs a paid API account. For you, running the demo,
that is fine. For other people running this open-source app, Opus 4.8 or Sonnet 5 are cheaper and
more universally available. The fallback chain already handles this: if Fable is unavailable, it
drops to Opus. Worth considering making the default configurable, with Fable as the opt-in "best
quality" pick.

## Sources

- HF datasets library (load_dataset): https://huggingface.co/docs/datasets
- HF Hub dataset search/list API: https://huggingface.co/docs/huggingface_hub
- Anthropic pricing: https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI pricing: https://developers.openai.com/api/docs/pricing and https://openai.com/api/pricing
- Datasets referenced inline below (each links to its Hugging Face page).

## 1. Preset dataset shortlist

Criteria: instruction or Q/A shaped (so it maps to our question/answer with little work),
permissive license (Apache or CC-BY preferred for a tool others may run commercially), and narrow
enough that fine-tuning a small Llama on it shows a visible behavior shift. We import a small slice
(50-100 rows), not the whole thing.

- General instruction, databricks/databricks-dolly-15k. About 15k human-written instruction/response
  pairs across categories. License CC BY-SA 3.0 (commercial OK with attribution). Fields: instruction,
  context, response. A clean, safe baseline preset.
- General assistant, OpenAssistant/oasst1 (or oasst2). Human conversation trees, Apache 2.0 (fully
  permissive). Needs a little shaping (extract prompt/response turns) but the license is the cleanest.
- Medical, one of: medalpaca/medical_meadow_medqa (free-form medical board Q/A), fedml/PubMedQA_instruction
  (PubMedQA reshaped to instruction form, question plus long answer), or MedQuAD (37 question types on
  diseases, drugs, tests). Medical is the crowd-pleaser domain; check the exact license on the chosen one
  (MedQuAD has some subsets removed for copyright).
- Finance, Josephgflowers/Finance-Instruct-500k. Apache 2.0, system/user/assistant fields, finance Q/A
  and reasoning. Top pick for finance: permissive and already in our shape. Alternative:
  sujet-ai/Sujet-Finance-Instruct-177k (Apache 2.0).
- Legal, asm3515/legal-clause-instruction-Tunning (Apache 2.0, commercial OK) for clause understanding,
  or AdaptLLM/law-LLM for broader legal reading-comprehension turned into conversation. Caution:
  pile-of-law is large and tempting but is CC BY-NC-SA (non-commercial) and asks not to be indexed, so
  avoid it for anything with a commercial path.

Interesting extra to consider: a "latest research" flavored set (for example a medical or scientific
Q/A dataset built from recent papers) is a compelling demo because it teaches the small model something
its base clearly does not know. We can pick one during the build.

License is the gating factor. For a project that may host and monetize later, prefer Apache 2.0 and
CC-BY; treat CC-BY-NC (non-commercial) and unclear licenses as demo-only or skip.

## 2. Hugging Face integration (import and browse)

Loading a dataset. The datasets library does the work:

    from datasets import load_dataset
    ds = load_dataset("Josephgflowers/Finance-Instruct-500k", split="train", streaming=True)
    rows = list(itertools.islice(ds, 100))

streaming=True avoids downloading the whole set to grab 100 rows. Then map each row's fields to our
question and answer and insert as qa_pairs.

The field-mapping problem. Every dataset names its fields differently: dolly uses instruction/response,
Finance-Instruct uses system/user/assistant, PubMedQA_instruction uses question/answer, Sujet uses
user_prompt/answer. So the import cannot assume field names. Two clean options: (a) each preset carries
a small mapping in our config (dataset id plus which field is the question and which is the answer), or
(b) the import endpoint takes the question-field and answer-field names as parameters. Presets use (a);
a future "import any dataset" feature uses (b).

Browsing datasets from the app (future feature). The Hub API lists and searches datasets:

    from huggingface_hub import HfApi
    api = HfApi()
    api.list_datasets(filter="task_categories:question-answering", sort="downloads", direction=-1, limit=20)

This powers a "search Hugging Face datasets" box later, filtered to Q/A tasks and sorted by popularity.
For the MVP we ship the curated presets; the browse box is a fast follow.

## 3. Generation prompting strategy

Goal: a plain-English use-case description in, N high-quality, non-repetitive Q/A pairs out, in strict
JSON we can parse straight into qa_pairs.

- System role sets the job and the rules: "You generate training data. Given a use case, produce diverse,
  factual question/answer pairs. Questions vary in phrasing and difficulty. Answers are correct, self
  contained, and concise. Output only JSON." Keeping the format rule in the system role, not the user
  turn, makes it stick.
- Few-shot: include 1-2 example pairs in the exact target JSON. Examples teach the shape and the tone far
  more reliably than description alone.
- Structured output, not hope. Both providers can force valid JSON:
  - OpenAI: Structured Outputs (response_format with a JSON schema) guarantees the reply matches the
    schema, so no brittle parsing.
  - Anthropic: define a tool whose input schema is our pair list and force that tool, or prefill the
    assistant turn with the opening bracket and parse. Either yields clean JSON.
  We validate the parsed JSON with a Pydantic model regardless, and retry once on a parse failure.
- Diversity and dedup. Ask for a spread of question types (factual, how-to, comparative, edge case) in the
  prompt. Then dedup on our side: normalize each question (lowercase, strip) and drop near-duplicates
  (exact match first; embedding-similarity is a nice later upgrade). Generating in a few smaller batches
  with slightly higher temperature gives more variety than one giant call, at a little more cost.
- Count control. Request N, but expect the model to sometimes return fewer; loop and top up until we have
  N unique pairs or hit a cap.

The output maps directly: each {question, answer} becomes a qa_pairs row under the target dataset. The
dataset's use_case_prompt column is the natural place to store the description that generated it.

## 4. Generator model and cost

Current model IDs and standard pricing per million tokens (input/output), July 3, 2026:

- Anthropic Fable 5 (claude-fable-5): $10 / $50. Most capable widely released Claude. Has safety
  classifiers that can refuse (a refusal with no output is not billed). Access was restored July 1 after
  a June suspension.
- Anthropic Opus 4.8 (claude-opus-4-8): $5 / $25. Half of Fable, the standard premium fallback.
- Anthropic Sonnet 5 (claude-sonnet-5): $2 / $10 introductory through Aug 31 2026, then $3 / $15. Strong
  and cheap, a good value option.
- OpenAI GPT-5.5 (flagship): $5 / $30. GPT-5.6 Sol also exists ($5 / $30) but is limited preview.
- OpenAI GPT-5.4-mini: $0.75 / $4.50. The cheap workhorse.

Rough cost per 100 pairs. Assume about 3k input tokens (prompt plus a couple of few-shot examples,
across a few batched calls) and about 12k output tokens (100 pairs, each question plus answer as JSON).
Output dominates.

- Fable 5: about $0.63 per 100 pairs.
- OpenAI GPT-5.5: about $0.38.
- Opus 4.8: about $0.32.
- Sonnet 5 (intro): about $0.13.
- GPT-5.4-mini: about $0.06.

Per 50 pairs is roughly half those; per 10 is roughly a tenth. Caveat: these are thinking-capable models
that can emit hidden reasoning tokens billed at the output rate, which can push cost up for reasoning-heavy
prompts; Q/A generation is light, so it should stay near these figures. Even the priciest option is well
under a dollar per 100 pairs, so the free-first-100 offer costs cents per user.

Decision (yours): default Fable 5, fall back to Opus 4.8, then OpenAI. Simple chain, top quality first.
Given the cost spread and Fable's access history, consider whether the shipped default for other users
should be Opus 4.8 or Sonnet 5, with Fable as an opt-in.

## 5. Key handling and mechanics

- API keys in environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY), loaded via our Pydantic Settings,
  never stored in the database or returned by the API.
- Provider SDKs: anthropic and openai Python packages (pipenv install). Both are simple chat-completions
  calls; the fallback chain is a try/except ladder across providers.
- New accounts get small trial credits; there is no permanent free API tier on either provider, so real
  generation needs a funded key. Fine for the demo.

## Recommended Phase 3 build order

1. Provider client module with the fallback ladder (Fable -> Opus 4.8 -> OpenAI) and JSON-schema output.
2. Generation endpoint: take a dataset id (or description) and a count, generate, dedup, insert qa_pairs.
3. Preset config (the 4-5 datasets above with their field mappings) and an import endpoint that loads N
   rows from a chosen preset and inserts them.
4. Later: a "browse Hugging Face" search box using the Hub list API, and embedding-based dedup.

## Open decisions

- Which exact preset per domain (pick from the shortlist during the build; confirm each license).
- Shipped default generator for other users: Fable (your pick) or a cheaper, more available default with
  Fable opt-in.
- Batch size and temperature for generation (diversity vs cost), tuned once we see output.
- Whether to expose the forward-looking roadmap items (hosting, sharing) publicly; parked for a roadmap pass.
