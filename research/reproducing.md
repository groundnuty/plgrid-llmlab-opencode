# Reproducing the measurements

Nothing here needs to be taken on trust. Every figure in
[models.md](models.md) comes from one of the commands below.

Set your key once:

```bash
export KEY=$(cat ~/.config/opencode/plgrid.key)     # or paste it inline
```

---

## Model list, function calling, cost, activity

The authoritative source for which models can drive an agent:

```bash
curl -sH "Authorization: Bearer $KEY" \
  https://llmlab.plgrid.pl/api/v1/models-plgrid-format | python3 -m json.tool
```

Per model it returns `function_calling_supported`, `is_active`, `is_commercial`,
`accessible` (grants) and `credits_per_token_price`.

A compact table:

```bash
curl -sH "Authorization: Bearer $KEY" \
  https://llmlab.plgrid.pl/api/v1/models-plgrid-format |
python3 -c '
import sys, json
for m in sorted(json.load(sys.stdin), key=lambda x: -(x["credits_per_token_price"] or 0)):
    print(f"{m[\"model_name\"]:44} FC={str(m[\"function_calling_supported\"]):5} "
          f"active={str(m[\"is_active\"]):5} {m[\"credits_per_token_price\"]:>6} {m[\"accessible\"]}")'
```

The OpenAI-compatible listing (`/api/v1/models`) carries no capability flags — use
the PLGrid-format endpoint instead.

## Real context limit

Ask for an absurd `max_tokens` and read the limit out of the error:

```bash
curl -sH "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3.6-27B","messages":[{"role":"user","content":"hi"}],
       "max_tokens":100000000}' \
  https://llmlab.plgrid.pl/api/v1/chat/completions
```

The response names either `maximum context length is N` or
`max_model_len=max_total_tokens=N`. This is how every `limit.context` in
`opencode.json` was derived — do not trust model cards, which frequently disagree
with what the deployment actually serves.

## Throughput

Median of three, identical token budget, so that model speed is not confounded with
how much work a model chooses to do:

```bash
python3 - <<'PY'
import json, time, statistics, urllib.request
K = open('/Users/you/.config/opencode/plgrid.key').read().strip()
URL = "https://llmlab.plgrid.pl/api/v1/chat/completions"
MODELS = ["zai-org/GLM-5.2-FP8", "zai-org/GLM-4.7-Flash",
          "Qwen/Qwen3.6-27B", "Qwen/Qwen3.6-35B-A3B",
          "Qwen/Qwen3-Coder-30B-A3B-Instruct", "google/gemma-4-31B"]
PROMPT = ("Write a Python function that reverses a linked list iteratively. "
          "Code only, no explanation.")

def once(m):
    body = {"model": m, "max_tokens": 300, "temperature": 0,
            "messages": [{"role": "user", "content": PROMPT}]}
    r = urllib.request.Request(URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {K}", "Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(r, timeout=300) as resp:
        d = json.loads(resp.read())
    el = time.time() - t0
    ct = (d.get("usage") or {}).get("completion_tokens") or 0
    return el, ct, ct / el if el else 0

for m in MODELS:
    runs = [once(m) for _ in range(3)]
    print(f"{m:38} {statistics.median(r[0] for r in runs):6.1f}s "
          f"{statistics.median(r[1] for r in runs):5.0f} tok "
          f"{statistics.median(r[2] for r in runs):6.1f} tok/s")
PY
```

**Interpretation warning.** A model that stops early looks fast on wall-clock but
produced less. Compare `tok/s`, and check the token count — two of the six models
stopped well before 300 tokens, so their latency figures are not comparable while
their throughput is.

## Tool-calling support, directly

```bash
curl -sH "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{
  "model":"Qwen/Qwen3-Coder-30B-A3B-Instruct","max_tokens":200,
  "messages":[{"role":"user","content":"What is the weather in Krakow? Use the tool."}],
  "tools":[{"type":"function","function":{"name":"get_weather",
    "parameters":{"type":"object","properties":{"city":{"type":"string"}},
                  "required":["city"]}}}],
  "tool_choice":"auto"}' \
  https://llmlab.plgrid.pl/api/v1/chat/completions | python3 -m json.tool
```

A model without a tool-call parser returns HTTP 400 mentioning
`--enable-auto-tool-choice`. **A 200 response is not proof of usable tool calling** —
check that `choices[0].message.tool_calls` is actually populated. This probe alone
gave a false positive on `QwQ-32B`; the gateway's `function_calling_supported` field
is the reliable answer.

## Reasoning channel

To see whether a model separates its chain-of-thought (and therefore needs
`interleaved`):

```bash
curl -sN -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"zai-org/GLM-4.7-Flash","messages":[{"role":"user","content":"say hi"}],
       "max_tokens":20,"stream":true}' \
  https://llmlab.plgrid.pl/api/v1/chat/completions | head -5
```

Look for `"reasoning_content"` in the delta objects.

## Vision

```bash
python3 - <<'PY'
import base64, json, urllib.request
K = open('/Users/you/.config/opencode/plgrid.key').read().strip()
img = base64.b64encode(open("some.png", "rb").read()).decode()
body = {"model": "Qwen/Qwen3-VL-8B-Instruct", "max_tokens": 60, "messages": [
    {"role": "user", "content": [
        {"type": "text", "text": "Describe this image in under 8 words."},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img}}]}]}
r = urllib.request.Request("https://llmlab.plgrid.pl/api/v1/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Authorization": f"Bearer {K}", "Content-Type": "application/json"})
print(json.loads(urllib.request.urlopen(r, timeout=180).read())["choices"][0]["message"]["content"])
PY
```

## Agentic benchmarks

See [benchmarks/README.md](benchmarks/README.md). Two fixtures plus differential
scorers; the important part of the method is that scoring happens on **hidden cases
the model never saw**, not on the test suite it was asked to make pass.

Three warnings, learned the hard way:

- **Run models sequentially.** Concurrent `opencode` instances contend on one SQLite
  database and fail with `database is locked`.
- **Score only after every run has finished.** Reading a working directory while the
  agent is still editing gives a half-written file and a wrong result.
- **Check the exit code is not your only signal.** `opencode run` occasionally exits
  0 having done nothing; assert on the artifact.

## Auditing what an agent actually did

The TUI does not reliably show subagent delegation. The session record does:

```bash
opencode session list
opencode export <session-id> | python3 -c '
import sys, json
def walk(o):
    if isinstance(o, dict):
        if o.get("tool"):
            inp = (o.get("state") or {}).get("input") or {}
            extra = " -> " + str(inp.get("subagent_type")) if o["tool"] == "task" else ""
            print("TOOL:", o["tool"] + extra)
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(json.load(sys.stdin))'
```

## Verifying config claims against OpenCode itself

Source references in [pitfalls.md](pitfalls.md) can be checked at HEAD:

```bash
curl -s https://raw.githubusercontent.com/anomalyco/opencode/dev/packages/opencode/src/session/prompt.ts        | grep -n 'steps ??'
curl -s https://raw.githubusercontent.com/anomalyco/opencode/dev/packages/opencode/src/session/llm/request.ts   | grep -n 'agent.prompt'
curl -s https://raw.githubusercontent.com/anomalyco/opencode/dev/packages/opencode/src/session/compaction.ts    | grep -n 'PRUNE_'
```

Note the repository moved: `sst/opencode` now redirects to `anomalyco/opencode`.
And when the prose documentation and the JSON schema disagree, the schema at
`https://opencode.ai/config.json` is the one that matches the binary.
