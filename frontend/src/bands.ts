export const BAND_COLORS: Record<string, string> = {
  Beginning: "#e11d48",
  Developing: "#d97706",
  Competent: "#2563eb",
  Accomplished: "#16a34a",
  "No Submission": "#71717a",
};

export const STATUS_COLORS: Record<string, string> = {
  not_started: "#a1a1aa",
  in_progress: "#d97706",
  completed: "#16a34a",
  not_submitted: "#71717a",
};

export function bandColor(band: string | null | undefined): string {
  return (band && BAND_COLORS[band]) || "#a1a1aa";
}
