"""S41 boundary guard: the api-agents import cuts from ADR-002.

ADR-002 rule 2 says api_agents may import stdlib + the provider SDKs + config
(read-only env), and must NEVER import models.*, schemas.*, database, or
core.security. That contract is only real if CI enforces it, so this test:

1. greps every module under backend/api_agents for the forbidden imports
   (ADR-002 explicitly prescribes a grep-based guard, not an AST framework);
2. pins the barrel: api_agents.__all__ is exactly the nine stable names from
   rule 1 of the ADR — nothing else is stable API;
3. proves the practical payoff the S24 Mac companion needs: api_agents
   imports cleanly in a bare interpreter without FastAPI or SQLAlchemy
   being pulled in.

No network, no keys — same hermetic rules as the S9 suite.
"""

import re
import subprocess
import sys
from pathlib import Path

import api_agents

BACKEND = Path(__file__).resolve().parents[1] / "backend"
API_AGENTS = BACKEND / "api_agents"

# Rule 2 forbidden set, verbatim from ADR-002. Anchored on the module root so
# "from models.user import ..." / "import database" / "from core import
# security" all trip it, while relative intra-package imports never match.
FORBIDDEN_IMPORT_PATTERNS = [
    re.compile(r"^\s*(?:from|import)\s+models(?:\.|\s|$)"),
    re.compile(r"^\s*(?:from|import)\s+schemas(?:\.|\s|$)"),
    re.compile(r"^\s*(?:from|import)\s+database(?:\s|$|\.)"),
    re.compile(r"^\s*(?:from|import)\s+core\.security(?:\.|\s|$)"),
    re.compile(r"^\s*from\s+core\s+import\s+.*\bsecurity\b"),
]

# Rule 1 barrel, exactly as ADR-002 lists it.
STABLE_API = {
    "call_json_tool",
    "chat_completion",
    "hosted_backends",
    "local_backends",
    "ollama_backend",
    "fan_out",
    "installed_ollama_models",
    "local_model_status",
    "prefer_order",
}


def _source_files():
    return sorted(p for p in API_AGENTS.rglob("*.py") if "__pycache__" not in p.parts)


def test_package_exists_and_has_sources():
    files = _source_files()
    # 6 moved modules + 3 __init__ files as of S41; never fewer (a file lost
    # in a refactor should fail loudly, not shrink the guard's coverage).
    assert len(files) >= 9, f"api_agents looks empty: {[f.name for f in files]}"


def test_api_agents_never_imports_tuner_sql_or_auth():
    offenders = []
    for path in _source_files():
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if any(p.search(line) for p in FORBIDDEN_IMPORT_PATTERNS):
                offenders.append(f"{path.relative_to(BACKEND)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "api_agents must not import models/schemas/database/core.security "
        f"(ADR-002 rule 2):\n" + "\n".join(offenders)
    )


def test_barrel_exports_exactly_the_stable_api():
    assert set(api_agents.__all__) == STABLE_API
    missing = [name for name in api_agents.__all__ if not hasattr(api_agents, name)]
    assert not missing, f"barrel advertises names it cannot supply: {missing}"


def test_api_agents_imports_without_the_web_stack():
    """The point of the cut: the S24 companion can import api_agents against
    on-device servers without dragging FastAPI/SQLAlchemy onto the box."""
    code = (
        "import sys; sys.path.insert(0, {backend!r});"
        "import api_agents;"
        "assert 'sqlalchemy' not in sys.modules, 'SQLAlchemy leaked into api_agents';"
        "assert 'fastapi' not in sys.modules, 'FastAPI leaked into api_agents';"
        "print('clean')"
    ).format(backend=str(BACKEND))
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0 and proc.stdout.strip() == "clean", (
        f"bare import of api_agents failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
