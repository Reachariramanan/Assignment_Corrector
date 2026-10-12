import { useState } from "react";
import type { AiSuggestion, RubricTrait } from "../api";

export interface TraitDraft {
  trait_id: number;
  level: number | null;
  comment: string;
  source: string;
}

interface Props {
  rubric: RubricTrait[];
  drafts: Record<number, TraitDraft>;
  onChange: (traitId: number, patch: Partial<TraitDraft>) => void;
  suggestions: Record<number, AiSuggestion>;
}

function levelOpacity(level: number, maxLevel: number): number {
  return 0.3 + 0.7 * (level / maxLevel);
}

function TraitRow({
  trait,
  draft,
  onChange,
  suggestion,
}: {
  trait: RubricTrait;
  draft: TraitDraft;
  onChange: (patch: Partial<TraitDraft>) => void;
  suggestion?: AiSuggestion;
}) {
  const [expanded, setExpanded] = useState(false);
  const maxLevel = Math.max(...trait.levels.map((l) => l.level), 1);

  return (
    <div className="border-b py-3.5 last:border-b-0" style={{ borderColor: "var(--dsa-border)" }}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="text-sm font-medium text-left hover:underline truncate"
          >
            {trait.name}
          </button>
          <span
            className="text-[10px] px-1.5 py-0.5 rounded-full shrink-0"
            style={{ background: "var(--dsa-soft)", color: "var(--dsa-muted)" }}
          >
            {trait.weight_pct}%
          </span>
        </div>
        <div className="flex rounded-md border overflow-hidden shrink-0" style={{ borderColor: "var(--dsa-border)" }}>
          {trait.levels.map((lvl, i) => {
            const selected = draft.level === lvl.level;
            return (
              <button
                key={lvl.level}
                type="button"
                onClick={() => onChange({ level: lvl.level, source: "manual" })}
                title={`${lvl.label}: ${lvl.descriptor}`}
                className="w-9 h-9 text-sm font-medium flex items-center justify-center transition-colors"
                style={{
                  borderLeft: i === 0 ? "none" : "1px solid var(--dsa-border)",
                  background: selected
                    ? `color-mix(in srgb, var(--dsa-accent) ${Math.round(levelOpacity(lvl.level, maxLevel) * 100)}%, var(--dsa-surface))`
                    : "transparent",
                  color: selected ? "var(--dsa-bg)" : "var(--dsa-text)",
                }}
              >
                {lvl.level}
              </button>
            );
          })}
        </div>
      </div>

      {expanded && (
        <div className="mt-2.5 grid grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
          {trait.levels.map((lvl) => (
            <div
              key={lvl.level}
              className="rounded-md border p-2"
              style={{
                borderColor: draft.level === lvl.level ? "var(--dsa-accent)" : "var(--dsa-border)",
                color: "var(--dsa-muted)",
              }}
            >
              <div className="font-medium mb-1" style={{ color: "var(--dsa-text)" }}>
                {lvl.level}. {lvl.label}
              </div>
              {lvl.descriptor}
            </div>
          ))}
        </div>
      )}

      {suggestion && (
        <div
          className="mt-2.5 rounded-md border p-2.5 text-xs"
          style={{ borderColor: "var(--dsa-accent)", background: "color-mix(in srgb, var(--dsa-accent) 8%, transparent)" }}
        >
          <div className="flex items-center justify-between mb-1 gap-2">
            <span className="font-medium">✦ AI suggests level {suggestion.level}</span>
            <button
              type="button"
              className="underline shrink-0"
              style={{ color: "var(--dsa-accent)" }}
              onClick={() => onChange({ level: suggestion.level, comment: suggestion.rationale, source: "ai_accepted" })}
            >
              Accept
            </button>
          </div>
          <p style={{ color: "var(--dsa-muted)" }}>{suggestion.rationale}</p>
        </div>
      )}

      <textarea
        className="mt-2 w-full rounded-md border px-2 py-1 text-xs bg-transparent"
        style={{ borderColor: "var(--dsa-border)", color: "var(--dsa-muted)" }}
        rows={draft.comment ? 2 : 1}
        placeholder="Add a note (optional)"
        value={draft.comment}
        onChange={(e) => onChange({ comment: e.target.value })}
      />
    </div>
  );
}

const EMPTY_DRAFT: TraitDraft = { trait_id: -1, level: null, comment: "", source: "manual" };

export default function RubricPanel({ rubric, drafts, onChange, suggestions }: Props) {
  return (
    <div>
      {rubric.map((trait) => (
        <TraitRow
          key={trait.id}
          trait={trait}
          draft={drafts[trait.id] ?? { ...EMPTY_DRAFT, trait_id: trait.id }}
          onChange={(patch) => onChange(trait.id, patch)}
          suggestion={suggestions[trait.id]}
        />
      ))}
    </div>
  );
}
