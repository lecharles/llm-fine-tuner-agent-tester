# Backend test suite (S9 / issue #12)

Hermetic pytest suite for the commit-train safety net: auth/me regressions,
settings/env precedence, the generation provider ladder (faked), the
`mlx_lm.server` lifecycle (faked subprocess/port), and the splash/SPA mount.
No network, no real provider calls, no real subprocesses.

## Running

From the repo root, using the same venv the `import main` smoke uses:

```bash
backend/.venv-smoke/bin/python -m pytest tests -q
```

pytest is not in the Pipfile yet (S10 CI will wire it); install locally with:

```bash
uv pip install --python backend/.venv-smoke/bin/python pytest
```

Runtime target: <10s on a laptop (currently ~5s, 37 tests).
