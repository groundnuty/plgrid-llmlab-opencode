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

The server refuses an output budget larger than the model's window, and the refusal
names the window. Send an impossible `max_tokens` and read the number out of the
error:

```bash
curl -sH "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3.6-27B","messages":[{"role":"user","content":"hi"}],
       "max_tokens":2000000000}' \
  https://llmlab.plgrid.pl/api/v1/chat/completions
```

The response names either `max_model_len=max_total_tokens=N` (current deployments)
or `maximum context length is N tokens` (older ones). Both are the *whole* window —
input plus output — not the usable output budget.

Use a value that cannot be a real context, with a trivially short prompt. If
`max_tokens` lands *inside* the window the request is not rejected: it runs and can
bill you for generating that many tokens. `100000000` was enough for every model
here, but `2000000000` removes the risk that some future deployment has a window
larger than the probe.

Loop the whole catalog and print a table (handles both error phrasings):

```bash
curl -sH "Authorization: Bearer $KEY" \
  https://llmlab.plgrid.pl/api/v1/models-plgrid-format |
python3 -c '
import sys, json, re, urllib.request, urllib.error
K = open("/Users/you/.config/opencode/plgrid.key").read().strip()
URL = "https://llmlab.plgrid.pl/api/v1/chat/completions"
for m in json.load(sys.stdin):
    body = json.dumps({"model": m["model_name"], "max_tokens": 2000000000,
                       "messages": [{"role": "user", "content": "hi"}]}).encode()
    req = urllib.request.Request(URL, data=body,
        headers={"Authorization": f"Bearer {K}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=120)
        print(f"{m[\"model_name\"]:44} no error (check manually)")
    except urllib.error.HTTPError as e:
        t = e.read().decode()
        g = re.search(r"max_total_tokens=(\d+)", t) or \
            re.search(r"maximum context length is (\d+) tokens", t)
        if g:
            print(f"{m[\"model_name\"]:44} context={g.group(1)}")
        else:
            print(f"{m[\"model_name\"]:44} unreachable: {json.loads(t).get(\"detail\", t)[:70]}")'
```

Two refinements over a bare probe:

- **The number is the total window, not the output budget.** Set `limit.output`
  well below it: OpenCode passes it verbatim as `max_tokens`, and the gateway
  enforces `input + max_tokens <= context`. `/models-plgrid-format` also advertises
  a `default_max_tokens_limit` for some models; where present it is a safe ceiling.
- **A row with no number is unreachable, not small.** Grant gating and
  `is_active: false` (HTTP 503) produce no context to measure until access is fixed.

## Throughput

Fixed output length, streamed, interleaved across models:

```bash
export LLMLAB_API_KEY=...        # or: set -a; . ./.env; set +a
python3 research/benchmarks/gateway.py throughput --repeats 5 \
  zai-org/GLM-5.2-FP8 deepseek-ai/DeepSeek-V4.1-Flash Qwen/Qwen3.6-27B \
  Qwen/Qwen3.6-35B-A3B Qwen/Qwen3-Coder-30B-A3B-Instruct google/gemma-4-31B
```

Every request forces exactly 300 output tokens (`min_tokens` and `max_tokens`
together, which the gateway honours), so a model that would stop early is measured
over the same length as one that would not. The columns are `tok/s`, the generation
rate between the first and last streamed token; `ttft s`, time to first token; and
`e2e tok/s`, tokens over total wall time. A `WARN token counts` status means
`min_tokens` was ignored and the row is not comparable.

**Interpretation warnings.**

- **A budget is not a length.** Without `min_tokens`, a model that stops after about 50
  tokens has its rate dominated by fixed latency. That understated `Qwen3-Coder-30B` at
  88 tok/s; at a forced 300 tokens its generation rate was 146.
- **The gateway is shared, and its load moves within minutes.** `Qwen3.6-35B-A3B`
  measured 54, 174 and 213 tok/s in three runs two minutes apart. The rounds are
  interleaved so a load spike hits every model, and the range column shows the spread:
  when two models' ranges overlap, do not rank them. A figure from one afternoon is a
  snapshot, not a property of the model.

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
check that `choices[0].message.tool_calls` is actually populated. The gateway's
`function_calling_supported` field is the right default, but it can lag the
deployment: `QwQ-32B` is listed without function calling and still returns structured
`tool_calls`. When the field and a populated `tool_calls` disagree, trust the
response.

## Reasoning channel

Whether a model separates its chain-of-thought (and so should be marked `reasoning`)
is a property of the deployment, not of the model card. Probe the streaming deltas
and print the fields that actually carry text:

```bash
curl -sN -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"zai-org/GLM-5.3-Flash","messages":[{"role":"user","content":"say hi"}],
       "max_tokens":30,"stream":true}' \
  https://llmlab.plgrid.pl/api/v1/chat/completions |
grep -o '"delta":{[^}]*}' | head
```

The gateway emits `"reasoning":"..."`.

`interleaved.field` is a separate question: it names the field OpenCode uses to send
past reasoning *back* on later turns. Whether that reaches the model depends on its
chat template, and the prompt token count shows it. Send the same history three times
— with no reasoning on the assistant turn, with it under `reasoning`, and under
`reasoning_content` — and compare `usage.prompt_tokens`:

```bash
for field in none reasoning reasoning_content; do
  extra=""; [ "$field" != none ] && extra=", \"$field\": \"The secret word is AMBERGRIS.\""
  curl -s -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "{
    \"model\": \"zai-org/GLM-5.3-Flash\", \"max_tokens\": 50, \"messages\": [
      {\"role\": \"user\", \"content\": \"Remember something for me.\"},
      {\"role\": \"assistant\", \"content\": \"I have noted it.\"$extra},
      {\"role\": \"user\", \"content\": \"Say OK.\"}]}" \
    https://llmlab.plgrid.pl/api/v1/chat/completions |
  python3 -c "import sys, json; print('$field', json.load(sys.stdin)['usage']['prompt_tokens'])"
done
```

The same count all three times means the template drops past reasoning; a higher
count means it renders it. The gateway accepts both field names, so the plugin sets

```js
"interleaved": { "field": "reasoning" }
```

A model that keeps its thinking inline in `content` (here `QwQ-32B` and
`Qwen3-Coder-30B-A3B`) has no separate channel: leave `reasoning` off rather than
pointing it at a field that never appears.

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

```bash
REPEATS=3 research/benchmarks/bench-all.sh     # report and TSV in research/benchmarks/results/
```

The warnings learned the hard way — isolate every run, keep the scorer out of reach,
never name the working directory after the package, run sequentially, score only
settled directories, guard the spec, distrust the exit code, repeat — are in the
[method notes](benchmarks/README.md#method-notes). The runner handles all of them.

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
