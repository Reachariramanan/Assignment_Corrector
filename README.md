# Submission Review Interface — By Digital Skills Academy

A local tool for grading Moodle assignment-export submissions against a weighted
rubric, with AI assistance throughout (Yukta agent framework + a local
sglang/Gemma server), object storage in MinIO, and a statistics dashboard.
SQLite storage, portable to another DB later.

## Agents (all via the vendored Yukta framework)

- **Grader** (`app/ai/grading_agent.py`) — one session per (student, module); a single
  holistic pass scores all rubric traits at once (per the rubric's own instruction),
  then takes reviewer follow-up questions in the same session.
- **File-kind classifier** (`app/ai/classifier.py`) — one-shot call per ambiguous
  submission file, used only when the filename alone doesn't say whether it's a
  worksheet/control note/declaration/etc.
- **Universal file parser** (`app/ai/file_parser_agent.py`) — for any submission file
  that isn't a plain .docx/.xlsx/.html, an agent picks from a small set of *fixed*
  conversion tools (pandoc, pdftotext, plain-text read, zip-listing, `file` type
  sniff) to extract readable content. Deliberately has **no** shell/arbitrary-code
  tool: submission files are untrusted (student-supplied) input, so every tool
  operates on the one path bound at call time, never on an LLM-supplied command
  string. Runs across multiple unknown files in parallel via a thread pool.
- **Prompt coach** (`app/ai/prompt_coach.py`) — only runs for students who filed their
  own AI Usage Disclosure; gives coaching on integration quality and prompting
  technique, never a plagiarism verdict or score.
- **Class assistant** (`app/ai/class_assistant.py`) — one persistent session per cohort,
  with read-only DB query tools (roster, trait averages, lowest scorers, a student's
  cross-module history) so it can answer questions grounded in real data, not guesses.

## Layout

```
backend/    FastAPI + SQLite (backend/data/reviews.db) + MinIO client
  vendor/yukta/   vendored copy of the Yukta agent framework (editable-installed)
frontend/   React + Vite + Tailwind + Recharts
imports/    extracted Moodle zips (per cohort/module) - also mirrored into MinIO
data/       source zip(s) as received
```

A dedicated MinIO container (`dsa-minio`, ports 19100/19101) stores every original
submission file and the source zip, independent of any other project's MinIO.

## One-time setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" openpyxl python-dotenv pydantic beautifulsoup4
pip install -e ./vendor/yukta

cp .env.example .env   # then edit .env with the real SGLANG_API_KEY

# start MinIO once (data persists in the dsa_paper_correction_minio_data volume)
docker run -d --name dsa-minio -p 19100:9000 -p 19101:9001 \
  -e MINIO_ROOT_USER=dsa_admin -e MINIO_ROOT_PASSWORD=dsa_local_dev_password \
  -v dsa_paper_correction_minio_data:/data \
  minio/minio server /data --console-address ":9001"
```

`.env` must point at whatever host port your sglang container actually publishes —
check with `docker ps` (the container's internal port is 8000, but it's commonly
published to a different host port). Do **not** include `/v1` in `SGLANG_BASE_URL`;
the Yukta `SGLangClient` appends `v1/...` itself.

```bash
cd frontend
npm install
```

## Importing a Moodle export zip

The fastest way is the "Upload" button in the app header (cohort name + module name +
the zip file). The CLI does the same thing and is useful for scripting/re-imports:

```bash
cd backend
source .venv/bin/activate
python -m app.ingest.import_zip ../data/<export>.zip --cohort "<cohort name>" --module "<module name>"
```

Re-running on the same zip is idempotent (upserts by student + filename). The
importer expects the standard Moodle export shape: a `*Case Study*.docx`, a
`*Sample Answer*`/`*Evaluator*` docx containing the rubric table (header row
starting with "Trait"), and a `Student Submissions/<Name>_<id>_assignsubmission_{file,onlinetext}/`
tree.

## Running

```bash
# terminal 1
cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8010

# terminal 2
cd frontend && npm run dev -- --host
```

Open http://localhost:5173, or from any other device on the same LAN,
`http://<this machine's LAN IP>:5173` (e.g. `http://192.168.200.23:5173` on this
machine - find yours with `hostname -I` or `ip addr`). `--host` on both commands binds
0.0.0.0 instead of just localhost; the backend's CORS is wide open (`*`) since this is
a LAN-only tool with no cookies/credentials involved.

## Notes

- AI-assist is a single holistic grading pass per student (all 6 rubric traits
  scored together in one call), matching the rubric's own instruction to grade
  holistically rather than per-task. Follow-up questions in the review page's
  chat box reuse the same Yukta agent/session, so the model remembers its own
  prior grading.
- `backend/data/` (SQLite DB + Yukta's own session storage) and `backend/.env`
  are gitignored — they hold local state and secrets respectively.
- Re-importing the same module upserts rubric traits by name (never delete-and-
  recreate) specifically so existing reviews/AI suggestions survive a re-import —
  `rubric_traits` has `ON DELETE CASCADE` dependents, so recreating trait rows
  would silently wipe graded work.
- The chat panel is a single right-side sheet (toggle tab on the screen edge) whose
  context follows what you're looking at: open it on a student's Review page and
  it's that student's grading conversation; anywhere else, it's the class-wide
  assistant.
