import { useEffect, useRef, useState } from "react";
import { matchPath, useLocation, useNavigate } from "react-router-dom";
import { api, type AssessAllProgress, type ChatMessage, type TraceStep } from "../api";
import { useModuleContext } from "../context/ModuleContext";
import ChatMarkdown from "./ChatMarkdown";
import TraceBlock from "./TraceBlock";

const REST_WIDTH_KEY = "dsa.chat.restWidthPct";
const PIN_KEY = "dsa.chat.pinned";
const REST_WIDTH_DEFAULT = 32;
const REST_WIDTH_MAX = 40;
const GENERATING_WIDTH = 60;
const MIN_DRAG_PX = 220;
const COLLAPSED_WIDTH_PX = 56;

function useStudentContext() {
  const location = useLocation();
  const reviewMatch = matchPath("/students/:studentId", location.pathname);
  return reviewMatch ? Number(reviewMatch.params.studentId) : null;
}

function Bubble({ role, content, trace }: { role: "user" | "assistant"; content: string; trace?: ChatMessage["trace"] }) {
  return (
    <div className={role === "user" ? "text-right" : "text-left"}>
      {role === "assistant" && (
        <div className="flex items-center gap-1.5 text-[11px] mb-1" style={{ color: "var(--dsa-muted)" }}>
          <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: "var(--dsa-green)", boxShadow: "0 0 0 3px color-mix(in srgb, var(--dsa-green) 25%, transparent)" }}
          />
          agent
        </div>
      )}
      {role === "assistant" && trace && trace.length > 0 && <TraceBlock trace={trace} />}
      <div
        className="inline-block rounded-2xl px-3 py-2 max-w-[70%] text-left"
        style={{
          background: role === "user" ? "var(--dsa-soft-2)" : "transparent",
          color: "var(--dsa-text)",
          border: role === "user" ? "1px solid var(--dsa-border)" : "none",
        }}
      >
        {role === "assistant" ? <ChatMarkdown content={content} /> : <span className="text-sm whitespace-pre-wrap">{content}</span>}
      </div>
    </div>
  );
}

export default function ChatPane() {
  const { cohortId, moduleId, refresh } = useModuleContext();
  const studentId = useStudentContext();
  const navigate = useNavigate();

  const [restWidthPct, setRestWidthPct] = useState<number>(() => {
    const v = localStorage.getItem(REST_WIDTH_KEY);
    const n = v ? Number(v) : REST_WIDTH_DEFAULT;
    return Number.isFinite(n) ? Math.min(Math.max(n, 0), REST_WIDTH_MAX) : REST_WIDTH_DEFAULT;
  });
  const [generating, setGenerating] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [zipDragOver, setZipDragOver] = useState(false);
  const [hovering, setHovering] = useState(false);
  const [pinned, setPinned] = useState<boolean>(() => localStorage.getItem(PIN_KEY) === "1");
  const containerRef = useRef<HTMLDivElement>(null);

  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [studentName, setStudentName] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [liveTrace, setLiveTrace] = useState<TraceStep[]>([]);
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [assessModuleId, setAssessModuleId] = useState<number | null>(null);
  const [assessProgress, setAssessProgress] = useState<AssessAllProgress | null>(null);
  const assessPollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (assessPollRef.current) window.clearInterval(assessPollRef.current);
    };
  }, []);

  async function startAssessment() {
    if (assessModuleId === null) return;
    const started = await api.startAssessAll(assessModuleId);
    setAssessProgress(started);
    if (!started.running) return;
    assessPollRef.current = window.setInterval(async () => {
      const status = await api.assessAllStatus(assessModuleId);
      setAssessProgress(status);
      if (!status.running && assessPollRef.current) {
        window.clearInterval(assessPollRef.current);
        assessPollRef.current = null;
      }
    }, 2500);
  }

  const contextKey = studentId ? `student:${studentId}` : `class:${cohortId}`;

  useEffect(() => {
    setHistory([]);
    if (studentId && moduleId !== null) {
      api.chatHistory(studentId, moduleId).then(setHistory);
      api.studentProfile(studentId).then((p) => setStudentName(p.student.name));
    } else if (cohortId !== null) {
      api.assistantHistory(cohortId).then(setHistory);
      setStudentName(null);
    }
  }, [contextKey, moduleId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, generating]);

  useEffect(() => {
    localStorage.setItem(REST_WIDTH_KEY, String(restWidthPct));
  }, [restWidthPct]);

  useEffect(() => {
    localStorage.setItem(PIN_KEY, pinned ? "1" : "0");
  }, [pinned]);

  useEffect(() => {
    if (!dragging) return;
    function onMove(e: MouseEvent) {
      const container = containerRef.current?.parentElement;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setRestWidthPct(Math.min(Math.max(pct, 0), REST_WIDTH_MAX));
    }
    function onUp() {
      setDragging(false);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging]);

  async function send() {
    if (!message.trim() || generating) return;
    const text = message.trim();
    setMessage("");
    setHistory((h) => [...h, { role: "user", content: text, created_at: new Date().toISOString() }]);
    setGenerating(true);
    setThinking(false);
    setLiveTrace([]);
    try {
      if (studentId && moduleId !== null) {
        await api.sendChatStream(studentId, moduleId, text, (e) => {
          if (e.type === "thinking") setThinking(true);
          else if (e.type === "tool_call" || e.type === "tool_end") {
            setThinking(false);
            setLiveTrace((t) => [...t, e as unknown as TraceStep]);
          } else if (e.type === "done") {
            const reply = (e as { reply?: string }).reply ?? "";
            const trace = ((e as { trace?: TraceStep[] }).trace ?? []) as TraceStep[];
            setHistory((h) => [...h, { role: "assistant", content: reply, trace, created_at: new Date().toISOString() }]);
          } else if (e.type === "error") {
            setHistory((h) => [
              ...h,
              { role: "assistant", content: `(error: ${(e as { message: string }).message})`, created_at: new Date().toISOString() },
            ]);
          }
        });
      } else if (cohortId !== null) {
        await api.assistantSendStream(cohortId, text, (e) => {
          if (e.type === "thinking") setThinking(true);
          else if (e.type === "tool_call" || e.type === "tool_end") {
            setThinking(false);
            setLiveTrace((t) => [...t, e as unknown as TraceStep]);
          } else if (e.type === "done") {
            const reply = (e as { reply?: string }).reply ?? "";
            const trace = ((e as { trace?: TraceStep[] }).trace ?? []) as TraceStep[];
            const student_id = (e as { student_id?: number | null }).student_id ?? null;
            setHistory((h) => [...h, { role: "assistant", content: reply, trace, created_at: new Date().toISOString() }]);
            if (student_id && student_id !== studentId) {
              navigate(`/students/${student_id}`);
            }
          } else if (e.type === "error") {
            setHistory((h) => [
              ...h,
              { role: "assistant", content: `(error: ${(e as { message: string }).message})`, created_at: new Date().toISOString() },
            ]);
          }
        });
      }
    } catch (e) {
      setHistory((h) => [
        ...h,
        { role: "assistant", content: `(error: ${e instanceof Error ? e.message : e})`, created_at: new Date().toISOString() },
      ]);
    } finally {
      setGenerating(false);
      setThinking(false);
      setLiveTrace([]);
    }
  }

  async function dropZip(f: File) {
    if (cohortId === null || generating) return;
    setHistory((h) => [...h, { role: "user", content: `📎 Dropped ${f.name}`, created_at: new Date().toISOString() }]);
    setGenerating(true);
    try {
      const result = await api.smartDropZip(f, cohortId);
      const reply =
        result.kind === "module_import"
          ? `Detected a module assignment export and imported it as **${result.module_name}**: ${result.students} students, ${result.files} files, ${result.rubric_traits} rubric traits` +
            (result.ai_classified_files ? ` (${result.ai_classified_files} file kinds auto-classified).` : ".")
          : `This doesn't look like a module export, so I read through it instead (${result.files_processed} files) and summarized it:\n\n${result.summary}`;
      setHistory((h) => [...h, { role: "assistant", content: reply, created_at: new Date().toISOString() }]);
      if (result.kind === "module_import") {
        refresh();
        setAssessModuleId(result.module_id);
        setAssessProgress(null);
      }
    } catch (e) {
      setHistory((h) => [
        ...h,
        { role: "assistant", content: `(error processing ${f.name}: ${e instanceof Error ? e.message : e})`, created_at: new Date().toISOString() },
      ]);
    } finally {
      setGenerating(false);
    }
  }

  if (cohortId === null) return null;

  const isOpen = generating || pinned || hovering;
  const widthPct = generating ? GENERATING_WIDTH : restWidthPct;
  const title = studentId ? `Grading chat${studentName ? ` — ${studentName}` : ""}` : "Class assistant";
  const placeholder = studentId ? "Why this score?" : 'Ask about the class, e.g. "how is Gaurav doing?"';
  const collapsed = !isOpen;

  return (
    <div
      ref={containerRef}
      className="relative shrink-0 h-full border-r flex flex-col"
      style={{
        width: collapsed ? `${COLLAPSED_WIDTH_PX}px` : `${widthPct}%`,
        minWidth: collapsed ? `${COLLAPSED_WIDTH_PX}px` : `${MIN_DRAG_PX}px`,
        borderColor: "var(--dsa-border)",
        background: "var(--dsa-surface)",
        transition: dragging ? "none" : "width 220ms ease",
        overflow: "hidden",
        zIndex: collapsed ? "auto" : 20,
      }}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes("Files")) {
          e.preventDefault();
          setZipDragOver(true);
        }
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setZipDragOver(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setZipDragOver(false);
        const dropped = e.dataTransfer.files?.[0];
        if (dropped && dropped.name.toLowerCase().endsWith(".zip")) dropZip(dropped);
      }}
    >
      {zipDragOver && (
        <div
          className="absolute inset-0 z-10 flex items-center justify-center text-sm font-medium pointer-events-none text-center px-2"
          style={{ background: "var(--dsa-accent-soft)", border: "2px dashed var(--dsa-accent)" }}
        >
          {collapsed ? "Drop" : "Drop zip to process…"}
        </div>
      )}
      {collapsed && (
        <button
          className="flex-1 flex flex-col items-center justify-center gap-2 text-lg"
          style={{ color: "var(--dsa-muted)" }}
          onClick={() => setPinned(true)}
          title="Open chat"
        >
          <span>💬</span>
          {generating && (
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: "var(--dsa-green)" }} />
          )}
        </button>
      )}
      {!collapsed && (
        <>
          <div className="px-3 py-2.5 border-b flex items-center justify-between shrink-0" style={{ borderColor: "var(--dsa-border)" }}>
            <div>
              <div className="text-sm font-medium">{title}</div>
              <div className="text-[11px]" style={{ color: "var(--dsa-muted)" }}>
                {studentId ? "context: this student's submission" : "context: whole class"}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setPinned((p) => !p)}
                title={pinned ? "Unpin (collapse on mouse-leave)" : "Pin open"}
                className="text-xs w-6 h-6 rounded-md flex items-center justify-center"
                style={{
                  background: pinned ? "var(--dsa-accent)" : "transparent",
                  color: pinned ? "var(--dsa-bg)" : "var(--dsa-muted)",
                  border: pinned ? "none" : "1px solid var(--dsa-border)",
                }}
              >
                📌
              </button>
              {generating && (
                <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ background: "var(--dsa-accent)", color: "var(--dsa-bg)" }}>
                  working…
                </span>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
            {history.length === 0 && (
              <p className="text-xs" style={{ color: "var(--dsa-muted)" }}>
                {studentId
                  ? "Ask the AI grader about this student's scores. It can see the research it did and the source documents."
                  : "Ask about the class - it can look up specific students, trait averages, or who's struggling where."}
              </p>
            )}
            {history.map((m, i) => (
              <Bubble key={i} role={m.role} content={m.content} trace={m.trace} />
            ))}
            {generating && (
              <div className="text-left">
                <div className="flex items-center gap-1.5 text-[11px] mb-1" style={{ color: "var(--dsa-muted)" }}>
                  <span
                    className="inline-block w-1.5 h-1.5 rounded-full animate-pulse"
                    style={{ background: "var(--dsa-green)", boxShadow: "0 0 0 3px color-mix(in srgb, var(--dsa-green) 25%, transparent)" }}
                  />
                  agent
                </div>
                {liveTrace.length > 0 && <TraceBlock trace={liveTrace} />}
                {thinking && (
                  <div className="text-xs animate-pulse" style={{ color: "var(--dsa-muted)" }}>
                    thinking…
                  </div>
                )}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
          {assessModuleId !== null && (
            <div className="px-3 py-2 border-t text-xs space-y-1.5 shrink-0" style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-soft)" }}>
              {!assessProgress && (
                <div className="flex items-center justify-between gap-2">
                  <span style={{ color: "var(--dsa-muted)" }}>Module imported.</span>
                  <button
                    onClick={startAssessment}
                    className="rounded-md px-2.5 py-1 text-xs shrink-0"
                    style={{ background: "var(--dsa-accent)", color: "var(--dsa-bg)" }}
                  >
                    Start Assessment
                  </button>
                </div>
              )}
              {assessProgress?.reason === "nothing_to_grade" && (
                <p style={{ color: "var(--dsa-muted)" }}>Nothing to assess - all students already graded.</p>
              )}
              {assessProgress && assessProgress.running && (
                <p>
                  Assessing… {assessProgress.done}/{assessProgress.total}
                  {assessProgress.current ? ` — ${assessProgress.current}` : ""}
                </p>
              )}
              {assessProgress && !assessProgress.running && assessProgress.reason !== "nothing_to_grade" && (
                <p style={{ color: "var(--dsa-accent)" }}>
                  Done: {assessProgress.done}/{assessProgress.total} graded
                  {assessProgress.errors.length > 0 ? `, ${assessProgress.errors.length} failed` : ""}.
                </p>
              )}
            </div>
          )}
          <div className="p-2 border-t flex gap-2 shrink-0" style={{ borderColor: "var(--dsa-border)" }}>
            <input
              className="flex-1 rounded-md border px-2 py-1.5 text-sm bg-transparent min-w-0"
              style={{ borderColor: "var(--dsa-border)" }}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder={placeholder}
              disabled={generating}
            />
            <button
              onClick={send}
              disabled={generating}
              className="rounded-md px-3 py-1.5 text-sm disabled:opacity-50 shrink-0"
              style={{ background: "var(--dsa-accent)", color: "var(--dsa-bg)" }}
            >
              Send
            </button>
          </div>
        </>
      )}

      {!collapsed && (
        <div
          onMouseDown={() => setDragging(true)}
          className="absolute top-0 right-0 h-full w-1.5 cursor-col-resize hover:bg-[var(--dsa-accent)]"
          style={{ opacity: dragging ? 1 : 0.001 }}
          title="Drag to resize"
        />
      )}
    </div>
  );
}
