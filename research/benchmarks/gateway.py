"""PLGrid Forge gateway helpers for bench-all.sh (usable on their own too).

  gateway.py models
      completion models as TSV: name, active, accessible, function calling
  gateway.py probe MODEL...
      one-token request per model: "name<TAB>ok" or "name<TAB><gateway's error>"
  gateway.py throughput [--repeats N] [--tokens N] MODEL...
      fixed-length streaming completions, interleaved rounds, medians and ranges

Throughput forces every completion to exactly --tokens output tokens (vLLM's
min_tokens together with max_tokens). Without that, a model that stops early is
credited with a higher or lower rate depending on how the fixed latency happens to
spread over the few tokens it produced. Generation rate (tok/s) is measured from the
first to the last streamed token; time to first token (ttft) is reported separately,
and e2e tok/s is tokens over total wall time.

Requires LLMLAB_API_KEY in the environment.
"""

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "https://llmlab.plgrid.pl/api/v1"
PROMPT = ("Write a Python function that reverses a linked list iteratively. "
          "Code only, no explanation.")


def api_key():
    key = os.environ.get("LLMLAB_API_KEY")
    if not key:
        sys.exit("error: LLMLAB_API_KEY is not set")
    return key


def request(path, body=None, timeout=300):
    headers = {"Authorization": f"Bearer {api_key()}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def gateway_error(exc):
    """The gateway's own explanation for an HTTP error, e.g. a grant rejection."""
    try:
        body = json.loads(exc.read())
    except (ValueError, OSError):
        return f"HTTP {exc.code}: {exc.reason}"
    error = body.get("error") if isinstance(body, dict) else None
    message = error.get("message") if isinstance(error, dict) else error
    message = message or (body.get("detail") if isinstance(body, dict) else None)
    return f"HTTP {exc.code}: {message or exc.reason}"


def cmd_models(_args):
    with request("/models-plgrid-format", timeout=60) as resp:
        rows = json.load(resp)
    if not isinstance(rows, list):
        sys.exit(f"error: unexpected catalog response: {str(rows)[:200]}")
    for m in rows:
        if m.get("model_type") != "completion":
            continue
        print("\t".join([
            m["model_name"],
            "1" if m.get("is_active") else "0",
            "1" if m.get("accessible") else "0",
            "1" if m.get("function_calling_supported") else "0",
        ]))


def cmd_probe(args):
    for model in args.models:
        body = {"model": model, "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}]}
        try:
            with request("/chat/completions", body, timeout=120) as resp:
                resp.read()
            status = "ok"
        except urllib.error.HTTPError as exc:
            status = gateway_error(exc)
        except OSError as exc:
            status = f"{type(exc).__name__}: {exc}"
        print(f"{model}\t{status}", flush=True)


def stream_once(model, tokens):
    body = {"model": model, "max_tokens": tokens, "min_tokens": tokens, "temperature": 0,
            "stream": True, "stream_options": {"include_usage": True},
            "messages": [{"role": "user", "content": PROMPT}]}
    t0 = time.monotonic()
    first = last = usage = None
    with request("/chat/completions", body) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            event = json.loads(line[5:])
            usage = event.get("usage") or usage
            for choice in event.get("choices") or []:
                delta = choice.get("delta") or {}
                if delta.get("content") or delta.get("reasoning") or delta.get("reasoning_content"):
                    last = time.monotonic()
                    if first is None:
                        first = last
    end = time.monotonic()
    if first is None:
        raise RuntimeError("no tokens were streamed")
    generated = (usage or {}).get("completion_tokens")
    if not generated:
        raise RuntimeError("the stream carried no usage block")
    rate = (generated - 1) / (last - first) if last > first else float("nan")
    return {"tokens": generated, "ttft": first - t0, "rate": rate, "e2e": generated / (end - t0)}


def cmd_throughput(args):
    # The gateway is shared and its load moves within minutes, so rounds are
    # interleaved across models (a load spike hits every model, not one) and the
    # min-max range is printed next to the median.
    runs = {model: [] for model in args.models}
    failed = {}
    for rnd in range(1, args.repeats + 1):
        for model in args.models:
            if model in failed:
                continue
            print(f"round {rnd}/{args.repeats}: {model}", file=sys.stderr, flush=True)
            try:
                runs[model].append(stream_once(model, args.tokens))
            except urllib.error.HTTPError as exc:
                failed[model] = f"UNREACHABLE {gateway_error(exc)[:100]}"
            except (OSError, ValueError, RuntimeError) as exc:
                failed[model] = f"FAIL {type(exc).__name__}: {str(exc)[:90]}"

    print(f"{'model':44} {'tokens':>6} {'ttft s':>6} {'tok/s':>7} {'range':>11} {'e2e tok/s':>9}  status")
    for model in args.models:
        if model in failed:
            print(f"{model:44} {'-':>6} {'-':>6} {'-':>7} {'-':>11} {'-':>9}  {failed[model]}")
            continue
        got = runs[model]
        short = [r["tokens"] for r in got if r["tokens"] != args.tokens]
        status = "ok" if not short else f"WARN token counts {short}: min_tokens not honoured"
        med = {k: statistics.median(r[k] for r in got) for k in ("tokens", "ttft", "rate", "e2e")}
        spread = f"{min(r['rate'] for r in got):.0f}-{max(r['rate'] for r in got):.0f}"
        print(f"{model:44} {med['tokens']:6.0f} {med['ttft']:6.2f} {med['rate']:7.1f} {spread:>11} "
              f"{med['e2e']:9.1f}  {status}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("models").set_defaults(func=cmd_models)
    probe = sub.add_parser("probe")
    probe.add_argument("models", nargs="+")
    probe.set_defaults(func=cmd_probe)
    throughput = sub.add_parser("throughput")
    throughput.add_argument("--repeats", type=int, default=5)
    throughput.add_argument("--tokens", type=int, default=300)
    throughput.add_argument("models", nargs="+")
    throughput.set_defaults(func=cmd_throughput)
    args = parser.parse_args()
    try:
        args.func(args)
    except (OSError, ValueError) as exc:
        sys.exit(f"error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
