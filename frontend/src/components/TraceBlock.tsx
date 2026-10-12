import { useState } from "react";
import type { TraceStep } from "../api";

function summarizeArgs(args: Record<string, unknown>): string {
  const parts = Object.entries(args).map(([k, v]) => `${k}=${JSON.stringify(v)}`);
  return parts.join(", ");
}

const GLYPHS: Record<string, string> = {
  list_files: "◌",
  read_file: "⌕",
  describe_file: "◌",
  try_pandoc: "⌕",
  try_pdftotext: "⌕",
  try_read_as_text: "⌕",
  try_list_zip_contents: "⌕",
  student_summary: "⌕",
  list_students: "◌",
  trait_averages: "◌",
  lowest_scorers: "◌",
};

function glyphFor(tool: string): string {
  return GLYPHS[tool] ?? "⚙";
}

function resultSummary(result: unknown): string {
  if (result && typeof result === "object" && "error" in (result as Record<string, unknown>)) {
    return `✗ ${String((result as Record<string, unknown>).error)}`;
  }
  const str = typeof result === "string" ? result : JSON.stringify(result);
  return `✓ ${str.length > 80 ? str.slice(0, 80) + "…" : str}`;
}

export default function TraceBlock({ trace }: { trace: TraceStep[] }) {
  const [expanded, setExpanded] = useState<number | null>(null);
  if (!trace || trace.length === 0) return null;

  return (
    <div className="space-y-1.5 mb-2">
      {trace.map((step, i) => {
        const isOpen = expanded === i;
        return (
          <div
            key={i}
            className="rounded-[10px] border overflow-hidden"
            style={{ borderColor: "var(--dsa-border)", background: "var(--dsa-surface)" }}
          >
            <button
              className="w-full text-left flex items-center gap-2 px-3"
              style={{ minHeight: 34 }}
              onClick={() => setExpanded(isOpen ? null : i)}
            >
              <span style={{ color: "var(--dsa-muted)" }}>{glyphFor(step.tool)}</span>
              <span
                className="text-[11px] font-semibold uppercase"
                style={{ color: "var(--dsa-muted)", letterSpacing: "0.04em" }}
              >
                {step.tool.replace(/_/g, " ")}
              </span>
              {summarizeArgs(step.args) && (
                <span className="truncate text-[11px] font-mono" style={{ color: "var(--dsa-faint)" }}>
                  ({summarizeArgs(step.args)})
                </span>
              )}
              <span className="ml-auto shrink-0 text-[10px]" style={{ color: "var(--dsa-faint)" }}>
                {step.duration_ms}ms
              </span>
              <span
                className="shrink-0 text-[10px]"
                style={{
                  color: "var(--dsa-faint)",
                  transform: isOpen ? "rotate(180deg)" : "none",
                  transition: "transform 0.16s ease",
                }}
              >
                ⌄
              </span>
            </button>
            {isOpen && (
              <div className="px-3 pb-2.5 pl-8">
                <div className="text-[11px] font-mono" style={{ color: "var(--dsa-green)" }}>
                  {resultSummary(step.result)}
                </div>
                <pre
                  className="mt-1 whitespace-pre-wrap break-words text-[10px] font-mono"
                  style={{ color: "var(--dsa-faint)" }}
                >
                  {JSON.stringify(step.result, null, 2)}
                </pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
