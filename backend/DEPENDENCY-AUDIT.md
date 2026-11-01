# Dependency Audit — S44 (2026-11-01)

Scope: the backend runtime environment (`backend/.venv-smoke`, Python 3.12.3,
78 distributions — the same package set `backend/Pipfile` resolves). Method:
version enumeration via `importlib.metadata`, batched against the OSV API
(`api.osv.dev/v1/querybatch`), with per-advisory detail lookups. pip-audit is
not installed in the smoke venv and has no offline DB, so OSV-over-HTTPS was
the live source of truth at audit time.

## Result

No exploitable-at-this-deployment critical vulnerabilities. 3 packages flagged,
64 clean, including the high-churn core stack: fastapi 0.141.1,
starlette 1.6.0, pydantic 2.13.5, SQLAlchemy 2.0.53, cryptography 50.0.1,
requests 2.34.2, urllib3 2.8.0, aiohttp 3.14.5, python-multipart 0.0.32.

| Package | Flag | Applicability |
|---|---|---|
| python-jose 3.5.0 | GHSA-3qf3-8w2g-rqmx / PYSEC-2026-4298 (algorithm-confusion guard bypassed by DER-encoded public keys) | NOT APPLICABLE as deployed: `core/security.py` decodes with `algorithms=[settings.jwt_algorithm]` and HS256 symmetric HMAC only — no EC/RSA public-key path is ever exercised. |
| ecdsa 0.19.2 | GHSA-wj6h-64fc-37mp / PYSEC-2026-1325 (Minerva timing attack, P-256) | Transitive of python-jose for EC key support, which we don't use (see above). |
| filelock 3.32.6 | 13 GHSA/PYSEC advisories; fixes land in 4.0.9 / 4.2.1 | Transitive of datasets/huggingface_hub. Windows-oplock and local-attacker preconditions; backend runs single-tenant on the Linux VPS and only uses filelock indirectly during dataset imports. |

## Follow-ups (backlog, not this slice)

- Bump filelock past 4.2.1 at the next `pipenv lock` refresh (needs network +
  pipenv on the Mac or VPS; smoke venv has no pip).
- passlib 1.7.4 is unmaintained; the `bcrypt==4.0.1` pin in Pipfile exists only
  for passlib compatibility. Replace CryptContext with direct bcrypt calls in a
  future slice, then unpin bcrypt.
- Re-check python-jose when GHSA-3qf3-8w2g-rqmx ships a fix; if the team ever
  enables asymmetric JWTs, this becomes a real blocker and the swap to PyJWT or
  authlib should happen first.

## Notes

- No credentials, tokens, or instance endpoints appear in this file or the
  audit artifacts; the OSV queries sent package names/versions only.
