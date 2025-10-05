# signal_noise Quick Start

## Environment Setup
1. Create the virtual environment: `python -m venv .venv`
2. Activate it (macOS/Linux): `source .venv/bin/activate`
3. Upgrade pip: `python -m pip install --upgrade pip`
4. Install dependencies: `pip install -r requirements.txt`

## Secrets
- Copy `.env.example` to `.env`
- Fill in real credentials (keep `.env` out of version control)
- `python-dotenv` loads these variables at runtime

## Tooling
- Tests: `pytest`
- Lint: `ruff check .`
- Type check: `mypy .`

Source code lives in `src/`; place new agents under `src/agents/`. Tests belong in `tests/`. Update `.env.example` and `requirements.txt` whenever secrets or dependencies change.