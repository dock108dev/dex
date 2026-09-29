# Vintage 251

A local Pokémon collection app for tracking physical copies, completing collecting
goals, reviewing card photos and exploring spoiler-controlled sample hunts.
The current supported use is a single user on localhost; public hosting and an
invited-user rollout are not qualified.

## Try it locally

Requires Python 3.12 or later and uv. From a checkout, create a **new synthetic demo**
outside the repository. This generates test accounts, catalog entries, copies and
photos without reading an existing collection or calling a recognition provider.

```sh
uv sync --locked --extra dev
export DEX_DEMO_ROOT="$HOME/.local/share/dex-synthetic-demo"
uv run python -m pokemon_hunter.beta.synthetic --output "$DEX_DEMO_ROOT"
uv run python -m pokemon_hunter.beta.cli --root "$DEX_DEMO_ROOT" serve
```

Open [Overview](http://127.0.0.1:8011/overview/). Use username `admin` and its generated
password from `credentials.json` in the private demo directory. Keep that file
private. The seed refuses an existing directory; on subsequent launches run only
`serve`. Stop the server with Ctrl-C. Port 8011 must be free.

The demo uses simulated recognition. It has no price guides or hunt snapshots;
those results remain unavailable. [Local development](docs/local-development.md)
explains existing installations, configuration and tests. The [original app](docs/ORIGINAL_APP.md)
remains available with its separate JSON ownership and history.

## Capabilities and limits

- Physical copies, intentional duplicates, binders, goals, import/export and undo.
- Private photo uploads, manual matching, provisional entries and explicit confirmation.
- Reviewed catalog publication and rollback; uncertain identity stays visible.
- Sample and saved hunts with explicit spoiler reveal; no live authenticated search.
- Conditional price-guide estimates when suitable dated evidence exists, not appraisals.

Photo recognition can explicitly use an OpenAI API key or a compatible authenticated
Codex CLI. Both send images to OpenAI; neither mode is enabled by this quickstart.
Real-card accuracy is unmeasured. See [photo entry](docs/photo-entry.md).

## Development

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

For focused changes, select the relevant test files. Tests use temporary synthetic
state. See [CI](docs/CI.md), [architecture and data ownership](docs/SSOT.md),
[security](docs/SECURITY.md), [failure recovery](docs/ERROR_HANDLING.md), and
[optional staging operations](docs/operations.md).
