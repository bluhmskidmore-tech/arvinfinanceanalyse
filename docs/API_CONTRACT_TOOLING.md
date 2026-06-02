# API Contract Tooling

MOSS has a lightweight OpenAPI contract surface for local and CI checks.

## Commands

Export the FastAPI OpenAPI document:

```powershell
python scripts/api_contract_check.py export-openapi --output .codex-tmp/openapi.json
```

Lint the exported contract with Spectral:

```powershell
cd frontend
npm run lint:openapi
```

Print the Schemathesis smoke command:

```powershell
python scripts/api_contract_check.py schemathesis-command
```

## Boundary

Spectral is wired into the frontend toolchain and CI because it does not conflict
with the Python test stack. Schemathesis is intentionally left as an external
tool command for now: current Schemathesis 4.18.x requires `pytest>=9`, while
this backend pins `pytest<9` for the existing suite.
