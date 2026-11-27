"""S62 (Model serving 1): `llmtuner serve` — the fused model → Ollama lane.

Two things, in one command:
1. Generate the Modelfile for a fused model (GGUF file or a fused dir that
   contains one), using the exact same builder the backend endpoint
   `GET /api/fine-tuned-models/{id}/modelfile` uses (training.modelfile —
   no second implementation to drift).
2. Run the import smoke. Default is the OFFLINE smoke (validate the file the
   way ollama's parser would — FROM first, real path, known QUANTIZE),
   because the VPS box has no Ollama. `--create` is the REAL smoke for the
   Mac: it runs `ollama create <tag> -f <Modelfile>` and then confirms the
   tag landed in `ollama list`.

Paths to know:
  --path   explicit GGUF file or fused dir
  --run-id backend/_training_runs/<id>/fused_model (the runner's workspace)
  --latest the highest-numbered run that has a fused_model dir
  --name / --tag / --quantize / --out / --create

Exit codes: 0 created or Modelfile written+smoked; 1 bad input, missing
GGUF, failed validation, missing/failed Ollama.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Repo-layout import of the shared builder (same assumption companion.py
# makes about the checkout it ships in): cli/llmtuner/serve.py -> repo root.
REPO = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from training.modelfile import (  # noqa: E402
    NO_GGUF_HINT,
    build_modelfile,
    find_gguf,
    ollama_tag,
    validate_modelfile,
)

TRAINING_ROOT = BACKEND_DIR / "_training_runs"


def resolve_source(path: str, run_id: int, latest: bool) -> tuple[Path | None, str]:
    """Turn the three mutually-relevant source flags into one directory/file.

    Returns (resolved path or None, human-readable error). --latest beats
    --run-id beats --path only in the sense that the CLI enforces one flag;
    here we just evaluate whichever is set."""
    if path:
        p = Path(path).expanduser()
        if not p.exists():
            return None, f"❌ No such file or directory: {p}"
        return p, ""
    if run_id > 0:
        p = TRAINING_ROOT / str(run_id) / "fused_model"
        if not p.exists():
            return None, f"❌ No fused model for run {run_id} at {p}"
        return p, ""
    if latest:
        if not TRAINING_ROOT.is_dir():
            return None, f"❌ No training runs found under {TRAINING_ROOT}"
        candidates = sorted(
            (d for d in TRAINING_ROOT.glob("*/fused_model") if d.is_dir()),
            key=lambda d: int(d.parent.name) if d.parent.name.isdigit() else -1,
        )
        if not candidates:
            return None, f"❌ No fused_model dirs under {TRAINING_ROOT}"
        return candidates[-1], ""
    return None, "❌ Nothing to serve: pass --path, --run-id, or --latest"


def _ollama_available() -> bool:
    return shutil.which("ollama") is not None


def _listed_tag(name: str, list_stdout: str) -> bool:
    """Did `ollama list` actually show the tag we just created?

    S70 (consuming the S62 serve feedback): real `ollama list` output ALWAYS
    shows models as `name:tag` — `ollama create ft-foo` lands as
    `ft-foo:latest` — but the tag we passed may or may not carry an explicit
    `:tag` part. The S62 fakes used bare-name rows, so VPS tests never saw
    the mismatch; on a real Mac the confirmation would always fail with
    "create succeeded but not in `ollama list`" after a perfectly good
    import. Match the first column of each data row: exact equality, or the
    implicit `:latest` ollama appends to an untagged create.
    """
    for line in list_stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        entry = fields[0]
        if entry == "NAME":  # ollama's own column header
            continue
        if entry == name or (":" not in name and entry == f"{name}:latest"):
            return True
    return False


def serve_command(
    path: str = "",
    run_id: int = 0,
    latest: bool = False,
    name: str = "",
    tag: str = "",
    quantize: str = "",
    out: str = "",
    create: bool = False,
) -> int:
    """Body of `llmtuner serve`. Returns the process exit code."""
    source, err = resolve_source(path, run_id, latest)
    if source is None:
        print(err)
        return 1

    gguf = find_gguf(source)
    if gguf is None:
        print(f"❌ No GGUF reachable from {source}")
        print(f"   {NO_GGUF_HINT}")
        return 1

    display_name = name or (
        source.parent.name if source.name == "fused_model" and source.is_dir()
        else source.stem if source.is_file()
        else source.name
    )
    ollama_name = tag or ollama_tag(display_name)
    q = quantize.strip().upper() or None

    if out:
        modelfile_dir = Path(out).expanduser()
        if modelfile_dir.is_file():
            modelfile_dir = modelfile_dir.parent
    else:
        modelfile_dir = gguf.parent if str(gguf.parent) else Path(".")
    modelfile_dir.mkdir(parents=True, exist_ok=True)
    modelfile_path = modelfile_dir / "Modelfile"
    content = build_modelfile(
        gguf, quantize=q,
        notes=f"generated by llmtuner serve from {gguf}",
    )
    modelfile_path.write_text(content, encoding="utf-8")

    print(f"📝 Modelfile → {modelfile_path}")
    for line in content.rstrip("\n").splitlines():
        print(f"   {line}")

    problems = validate_modelfile(content, base_dir=modelfile_dir)
    if problems:
        print("❌ Offline import smoke FAILED:")
        for problem in problems:
            print(f"   · {problem}")
        return 1
    print("✅ Offline import smoke passed (FROM resolvable, directives valid)")

    if not create:
        print()
        print(f"   Next (on the machine with the GGUF + Ollama):")
        print(f"   ollama create {ollama_name} -f {modelfile_path}")
        print("   ...or run this again with --create.")
        return 0

    if not _ollama_available():
        print("❌ `ollama` not on PATH — cannot --create. (See `llmtuner doctor`.)")
        return 1

    create_argv = ["ollama", "create", ollama_name, "-f", str(modelfile_path)]
    if q:
        print(f"🏗️  Creating {ollama_name} (QUANTIZE {q} rides the Modelfile)...")
    else:
        print(f"🏗️  Creating {ollama_name}...")
    result = subprocess.run(create_argv, cwd=modelfile_dir, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ ollama create exited {result.returncode}")
        tail = (result.stderr or result.stdout or "").strip()[-800:]
        if tail:
            print(f"   {tail}")
        return 1

    listing = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if _listed_tag(ollama_name, listing.stdout or ""):
        print(f"✅ Import smoke confirmed: `{ollama_name}` is live in `ollama list`")
        print(f"   Try it:  ollama run {ollama_name}")
        return 0
    print(f"❌ ollama create succeeded but {ollama_name} is not in `ollama list`")
    return 1
