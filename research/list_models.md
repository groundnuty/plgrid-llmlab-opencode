# `list_models.py`

A single-purpose script that lists every model published by the PLGrid LLM Lab
(Forge) gateway, together with the handful of properties that decide whether and how
you should use one: price, active/inactive, accessible/inaccessible, tool-calling
support, embedding, beta and non-commercial flags.

It exists so that humans **and language models** can answer "what can I run here, and
what can it do?" without scraping HTML or guessing from a model name. The output is a
plain fixed-width table, which is trivial to read in a terminal and equally easy for an
agent to parse or paste back into a reasoning step.

## Running it

From the repository root:

```bash
python3 research/list_models.py
```

It needs one credential, `LLMLAB_API_KEY`, either already exported or present in the
repo-root `.env` file (loaded via `python-dotenv`; the script searches upward from its
own location, so the `.env` stays at the root). `.env` is gitignored — never commit
the key.

Dependencies are `requests` and `python-dotenv`; both live in the project `venv/`.

```
Model Name                                         | Price (1M tokens)    | Tags
-------------------------------------------------------------------------------------
Qwen/Qwen3.6-27B                                   | 2.0                  | Active, Accessible, Non-commercial, FC, Beta
deepseek-ai/DeepSeek-V4.1-Flash                    | 4.0                  | Active, Accessible, Non-commercial, FC, Beta
zai-org/GLM-4.7-Flash                              | 2.5                  | Inactive, Accessible
```

## What it does

It issues one authenticated `GET` against
`https://llmlab.plgrid.pl/api/v1/models-plgrid-format` and prints one row per model.
That endpoint — not the OpenAI-style `/models` list — is the authoritative source for
the capability flags below.

The **price** column is the flat `credits_per_token_price` when the model has one;
otherwise it is formatted as `In: … / Out: …` from the split
`credits_per_input_token_price` / `credits_per_output_token_price` fields. If neither
is present it prints `N/A`.

The **tags** column is assembled from the response fields:

| Tag | Field | Meaning |
|---|---|---|
| `Active` / `Inactive` | `is_active` | Whether the gateway is currently serving it |
| `Accessible` / `Inaccessible` | `accessible` | Whether it is reachable with the account's grants |
| `Non-commercial` | `is_commercial == false` | Commercial use restricted; fine for research |
| `FC` | `function_calling_supported` | Can be used by tool-calling agents |
| `EMB` | `model_type == "embedding"` | An embedding model, not a chat model |
| `Beta` | `is_beta` | Flagged as beta by the operator |

Any other field in the response (for example `default_max_tokens_limit`,
`license_name`) is ignored by the script but is available from the same endpoint if
you need it.

## How an LLM can use it

The reason this is documented for agents, not just people:

- **Choose a model for a role.** Filter for `FC` before wiring a model into an
  OpenCode agent, so the agent is not handed a chat-only model.
- **Check reality before measuring.** Confirm a model is `Active` and `Accessible`
  before benchmarking it or probing its context window; the reproduction guide in
  [`reproducing.md`](reproducing.md) assumes this.
- **Regenerate the catalog.** The provider plugin `../.opencode/plugins/plgrid.js` and
  the roster in [`../README.md`](../README.md) are both derived from this same
  endpoint; this script is the quick way to see what changed.
- **Report capability limits honestly.** When asked "can this model do X?", the `FC`,
  `EMB`, `Non-commercial` and `Beta` tags are the facts, rather than assumptions from
  the model family name.

## Caveats

- `Accessible` reflects the account/grants as a whole. The gateway still routes
  requests through a **single default grant**, so a model tagged `Accessible` can
  still fail with `Model 'X' is not available for grant 'Y'`. See the known issues in
  [`../README.md`](../README.md).
- The script only reads; it makes no writes and has no side effects beyond one HTTP
  request.
- On missing key or network/HTTP failure it prints a message and exits with status 1,
  so it can be chained safely in a script.
