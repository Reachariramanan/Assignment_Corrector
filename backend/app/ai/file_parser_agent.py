"""Universal fallback file parser: for any submission file whose format we don't
already have a dedicated parser for (docx/xlsx/html), an agent picks from a small
set of FIXED, single-purpose conversion tools to see what extracts readable content.

Security note: submission files are untrusted input (student-supplied). Every tool
here operates on the one file path bound at call time via closure - never on an
LLM-supplied path or command string - and each tool runs one fixed, argument-list
subprocess call (no shell=True, no string interpolation into a command). There is
no arbitrary-shell or arbitrary-code-execution tool: that would let a crafted
submission prompt-inject the agent into running something harmful. If none of
these fixed converters produce anything, the file is reported as not parseable -
that is an acceptable outcome for an unusual format.
"""

import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from yukta import AgentConfig, SystemPrompt, Tool, ToolParameter, ToolProcessor, ToolType, create_agent

from app.ai.common import UsageCapture, agent_response, extract_json, new_llm_client

MAX_OUTPUT_CHARS = 6000
CMD_TIMEOUT = 15

FILE_PARSER_SYSTEM = """You are helping ingest one file from a student's assignment submission that isn't a \
plain .docx/.xlsx/.html (those are already handled elsewhere). You cannot see the file directly - use your \
tools to try to extract readable content from it. Try describe_file first to see what it is, then whichever \
conversion tool fits (try more than one if the first returns nothing useful).

Once you've extracted what you can, respond with ONLY a JSON object, no prose:
{{"html": "<simple HTML rendering, e.g. wrapped in <pre> or <p> tags>", "text": "<plain text extraction>", \
"description": "<one sentence on what this file is>"}}

If nothing extracts readable text (e.g. a photo, or a format none of your tools handle), set html/text to \
empty strings and only fill in "description".
"""


def _run(args: list[str]) -> dict:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=CMD_TIMEOUT)
        return {
            "stdout": proc.stdout[:MAX_OUTPUT_CHARS],
            "stderr": proc.stderr[:500],
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timed out after {CMD_TIMEOUT}s"}
    except FileNotFoundError as e:
        return {"error": f"Tool not installed: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _make_tools(path: Path) -> ToolProcessor:
    def describe_file() -> dict:
        return _run(["file", "--brief", str(path)])

    def try_pandoc(output_format: str = "plain") -> dict:
        fmt = output_format if output_format in ("html", "plain", "markdown") else "plain"
        return _run(["pandoc", str(path), "-t", fmt, "--wrap=none"])

    def try_pdftotext() -> dict:
        return _run(["pdftotext", str(path), "-"])

    def try_read_as_text() -> dict:
        try:
            return {"stdout": path.read_text(encoding="utf-8", errors="ignore")[:MAX_OUTPUT_CHARS]}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def try_list_zip_contents() -> dict:
        try:
            with zipfile.ZipFile(path) as zf:
                return {"stdout": "\n".join(zf.namelist()[:200])}
        except Exception as e:
            return {"error": f"Not a zip-based file: {e}"}

    processor = ToolProcessor()
    processor.add_tool(
        Tool(
            name="describe_file",
            description="Run the 'file' command to identify this file's actual type.",
            parameters=[],
            tool_type=ToolType.CUSTOM,
            function=describe_file,
        )
    )
    processor.add_tool(
        Tool(
            name="try_pandoc",
            description="Try converting this file with pandoc (works for many document formats: odt, rtf, epub, markdown, etc).",
            parameters=[
                ToolParameter(
                    name="output_format", type="string", description="One of: html, plain, markdown",
                    required=False, default="plain", enum=["html", "plain", "markdown"],
                )
            ],
            tool_type=ToolType.CUSTOM,
            function=try_pandoc,
        )
    )
    processor.add_tool(
        Tool(
            name="try_pdftotext",
            description="Try extracting text if this is a PDF.",
            parameters=[],
            tool_type=ToolType.CUSTOM,
            function=try_pdftotext,
        )
    )
    processor.add_tool(
        Tool(
            name="try_read_as_text",
            description="Try reading the raw file as plain UTF-8 text (works for .txt, .csv, .json, .md, code files).",
            parameters=[],
            tool_type=ToolType.CUSTOM,
            function=try_read_as_text,
        )
    )
    processor.add_tool(
        Tool(
            name="try_list_zip_contents",
            description="If this is a zip-based container format (pptx, odt, etc), list its internal file names.",
            parameters=[],
            tool_type=ToolType.CUSTOM,
            function=try_list_zip_contents,
        )
    )
    return processor


def parse_unknown_file(path: Path) -> dict[str, Any]:
    """Returns {"html": ..., "text": ..., "description": ...} - never raises; falls back
    to an empty/description-only result on any agent or parsing failure."""
    usage_capture = UsageCapture()
    agent = create_agent(
        name=f"file-parser-{path.name}",
        system_prompt=SystemPrompt(prompt_name="FileParser", prompt_text=FILE_PARSER_SYSTEM),
        llm_client=new_llm_client(temperature=0.1),
        tools_processor=_make_tools(path),
        config=AgentConfig(temperature=0.1, max_iter=8, verbose=False),
        callbacks=usage_capture,
    )
    try:
        result = agent.run(
            user_message=f"Parse this file (name: {path.name}) and return the JSON result.",
            reset_conversation=True,
        )
        parsed = extract_json(agent_response(result))
        return {
            "html": parsed.get("html", ""),
            "text": parsed.get("text", ""),
            "description": parsed.get("description", ""),
        }
    except Exception as e:
        return {"html": "", "text": "", "description": f"(auto-parsing failed: {e})"}


def parse_unknown_files_parallel(paths: list[Path], max_workers: int = 4) -> dict[Path, dict[str, Any]]:
    """Fans out parse_unknown_file across a thread pool - the sglang server accepts
    concurrent requests natively (max-running-requests set well above our batch sizes)."""
    if not paths:
        return {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(parse_unknown_file, paths))
    return dict(zip(paths, results))
