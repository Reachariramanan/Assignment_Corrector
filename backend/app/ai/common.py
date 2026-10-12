import json
import os
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from yukta import AgentCallbackHandler, AgentConfig, SystemPrompt, ToolProcessor, create_agent
from yukta.core.Clients.sglang_client import SGLangClient

load_dotenv()

YUKTA_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "yukta"
os.environ.setdefault("YUKTA_DATA_DIR", str(YUKTA_DATA_DIR))

SGLANG_BASE_URL = os.environ.get("SGLANG_BASE_URL", "http://localhost:11650")
SGLANG_API_KEY = os.environ.get("SGLANG_API_KEY", "")
SGLANG_MODEL = os.environ.get("SGLANG_MODEL", "gemma-4-26b-a4b-it")


class UsageCapture(AgentCallbackHandler):
    """Accumulates usage AND a step-by-step trace across every LLM/tool call in a run
    (a tool-calling agent may make several internal LLM calls per `run()`) -
    `last_usage` is the running total, `trace` is the ordered list of steps taken,
    surfaced in the UI so the reviewer can see what the agent actually did, not just
    its final answer."""

    def __init__(self) -> None:
        self.last_usage: dict[str, int] = {"tokens_prompt": 0, "tokens_completion": 0}
        self.trace: list[dict[str, Any]] = []
        self._tool_start_args: dict[str, Any] = {}
        # Set per-call (and cleared after) by the streaming routes to relay live events -
        # e.g. a queue.put - while the blocking agent.run() executes in a worker thread.
        # None in the normal (non-streaming) path, so this is a no-op cost otherwise.
        self.live_sink: Callable[[dict[str, Any]], None] | None = None

    def reset(self) -> None:
        self.last_usage = {"tokens_prompt": 0, "tokens_completion": 0}
        self.trace = []

    def _emit(self, event: dict[str, Any]) -> None:
        if self.live_sink is not None:
            try:
                self.live_sink(event)
            except Exception:
                pass

    def on_llm_start(self, messages: Any, tools: Any) -> None:
        self._emit({"type": "thinking"})

    def on_llm_end(self, response: Any) -> None:
        usage = getattr(response, "usage", None) or {}
        self.last_usage["tokens_prompt"] += usage.get("prompt_tokens", 0)
        self.last_usage["tokens_completion"] += usage.get("completion_tokens", 0)

    def on_tool_start(self, tool_name: str, args: dict[str, Any]) -> None:
        self._tool_start_args[tool_name] = args
        self._emit({"type": "tool_start", "tool": tool_name, "args": args})

    def on_tool_end(self, tool_name: str, result: Any, duration_ms: float) -> None:
        step = {
            "type": "tool_call",
            "tool": tool_name,
            "args": self._tool_start_args.pop(tool_name, {}),
            "result": result if isinstance(result, (dict, list, str, int, float, bool, type(None))) else str(result),
            "duration_ms": round(duration_ms, 1),
        }
        self.trace.append(step)
        self._emit({"type": "tool_end", **step})


def new_llm_client(temperature: float = 0.2, max_tokens: int = 8192) -> SGLangClient:
    # Explicit max_tokens matters: without it, a request that hits the server's own
    # default cutoff comes back with finish_reason="length", and Yukta's own
    # auto-continue-and-stitch logic for that case has produced malformed JSON at
    # the stitch boundary for longer multi-file dossiers. Giving it enough budget
    # to finish our (intentionally compact) JSON schemas in one completion avoids
    # needing that continuation path at all.
    return SGLangClient(
        model_name=SGLANG_MODEL,
        base_url=SGLANG_BASE_URL,
        api_key=SGLANG_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _top_level_json_candidates(text: str) -> list[str]:
    """String-aware brace matching: finds every substring that looks like a complete
    top-level {...} object, ignoring braces inside quoted strings."""
    candidates = []
    depth = 0
    start = None
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    candidates.append(text[start : i + 1])
    return candidates


def extract_json(text: str) -> dict[str, Any]:
    """Some completions get cut off mid-string on a length limit and the model's
    continuation restarts the whole JSON object rather than resuming the cut-off
    string - which leaves two (or more) concatenated {...} blobs in the response,
    the first truncated/malformed and the last one (hopefully) complete. So: try
    every top-level {...} candidate, last-to-first, and return the first one that
    actually parses. strict=False tolerates a literal newline/tab inside a string
    value instead of an escaped one, which models also sometimes emit."""
    candidates = _top_level_json_candidates(text)
    if not candidates:
        raise ValueError(f"No JSON object found in model response: {text[:500]}")
    errors = []
    for candidate in reversed(candidates):
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError as e:
            errors.append(str(e))
    raise ValueError(
        f"None of {len(candidates)} candidate JSON object(s) in the model response parsed. "
        f"Last error: {errors[-1] if errors else 'unknown'}. Response head: {text[:300]}"
    )


def agent_response(result: dict[str, Any]) -> str:
    """Safely extracts the final response text from agent.run()'s result dict. On normal
    completion it's {"response": ...}, but Yukta returns a *different* shape - no
    "response" key at all, just {"success": False, "error": ..., "iterations": ...,
    "tool_calls": ...} - when the agent hits its max_iter limit without producing a final
    answer. Reading result["response"] directly in that case raises a bare, confusing
    KeyError: 'response' instead of surfacing what actually went wrong."""
    if "response" in result:
        return result["response"]
    raise RuntimeError(result.get("error") or "agent did not produce a response (unknown reason)")


def run_oneshot(
    name: str,
    system_text: str,
    user_text: str,
    temperature: float = 0.2,
    tools_processor: ToolProcessor | None = None,
    max_iter: int | None = None,
) -> tuple[str, dict[str, int]]:
    """Stateless single-turn (or tool-augmented, multi-iteration) LLM call, no persisted memory."""
    usage_capture = UsageCapture()
    if max_iter is None:
        max_iter = 10 if tools_processor else 1
    agent = create_agent(
        name=name,
        system_prompt=SystemPrompt(prompt_name=name, prompt_text=system_text),
        llm_client=new_llm_client(temperature),
        tools_processor=tools_processor,
        config=AgentConfig(temperature=temperature, max_iter=max_iter, verbose=False),
        callbacks=usage_capture,
    )
    result = agent.run(user_message=user_text, reset_conversation=True)
    usage = dict(usage_capture.last_usage)
    return agent_response(result), usage
