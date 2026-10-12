const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export type StreamEvent =
  | { type: "thinking" }
  | { type: "tool_start"; tool: string; args: Record<string, unknown> }
  | { type: "tool_call" | "tool_end"; tool: string; args: Record<string, unknown>; result: unknown; duration_ms: number }
  | { type: "done"; [key: string]: unknown }
  | { type: "error"; message: string };

/** Parses a text/event-stream POST response (EventSource doesn't support POST bodies,
 * so this reads the fetch ReadableStream and splits on SSE's blank-line record separator). */
async function streamSSE(path: string, body: unknown, onEvent: (e: StreamEvent) => void): Promise<void> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? `Request failed: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const record = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = record.replace(/^data: /, "").trim();
      if (line) onEvent(JSON.parse(line));
    }
  }
}

export interface Cohort {
  id: number;
  name: string;
  created_at: string;
}

export interface ModuleSummary {
  id: number;
  cohort_id: number;
  name: string;
  imported_at: string;
}

export interface RubricLevel {
  level: number;
  label: string;
  descriptor: string;
}

export interface RubricTrait {
  id: number;
  name: string;
  weight_pct: number;
  sort_order: number;
  levels: RubricLevel[];
}

export interface StudentSummary {
  id: number;
  name: string;
  moodle_participant_id: string | null;
  status: "not_started" | "in_progress" | "completed" | "not_submitted";
  total_weighted_score: number | null;
  band: string | null;
}

export interface SubmissionFile {
  id: number;
  kind: string;
  original_filename: string;
  source_format: string;
  extracted_html: string;
}

export interface ReviewTrait {
  trait_id: number;
  name: string;
  weight_pct: number;
  level: number | null;
  comment: string | null;
  source: string | null;
}

export interface ReviewSummary {
  framing_note: string | null;
  total_weighted_score: number | null;
  band: string | null;
  status: string;
}

export interface ReviewsResponse {
  traits: ReviewTrait[];
  summary: ReviewSummary | null;
}

export interface AiSuggestion {
  trait_id: number;
  trait: string;
  level: number;
  rationale: string;
}

export interface AiAssistResponse {
  not_submitted: boolean;
  reason?: string;
  framing_note?: string;
  suggestions: AiSuggestion[];
}

export interface TraceStep {
  type: "tool_call";
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
  duration_ms: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  trace?: TraceStep[];
  created_at: string;
}

export interface TraitStat {
  trait_id: number;
  name: string;
  weight_pct: number;
  avg_level: number | null;
  scored_count: number;
  ai_avg_abs_delta: number | null;
  ai_accept_rate: number | null;
}

export interface ModuleStatistics {
  traits: TraitStat[];
  completion: {
    total_students: number;
    not_started: number;
    in_progress: number;
    completed: number;
    not_submitted: number;
  };
  weighted_score_distribution: number[];
  ai_usage: {
    total_prompt_tokens: number;
    total_completion_tokens: number;
    calls: number;
  };
}

export interface AiUsageAssessment {
  has_declaration: boolean | null;
  declared_tools?: string[];
  integration_quality?: string;
  coaching_note?: string;
  prompting_suggestions?: string[];
}

export interface StudentProfile {
  student: { id: number; name: string; moodle_participant_id: string | null; cohort_id: number };
  modules: {
    module_id: number;
    module: string;
    total_weighted_score: number | null;
    band: string | null;
    status: string;
    imported_at: string;
  }[];
  trait_history: { module: string; trait: string; level: number }[];
  average_weighted_score: number | null;
}

export interface CohortOverview {
  modules: {
    module_id: number;
    module: string;
    total_students: number;
    completed: number;
    avg_score: number | null;
  }[];
  overall_avg_score: number | null;
  ai_usage: { total_tokens: number; calls: number };
  ai_usage_coached_students: number;
}

export interface Dossier {
  dossier: {
    files_reviewed?: string[];
    per_task_evidence?: { task: string; found: boolean; evidence: string; gaps: string }[];
    notable_citations?: string[];
    overall_impression?: string;
  };
  review_draft: {
    traits?: {
      trait: string;
      weight_pct: number;
      level: number;
      level_label: string;
      earned_pct: number;
      reasoning_verbatim: string;
      open_question?: string;
    }[];
  } | null;
  files_read_count: number;
  created_at: string;
}

export interface UploadResult {
  cohort: string;
  module: string;
  module_id: number;
  rubric_traits: number;
  students: number;
  files: number;
  ai_classified_files: number;
}

export interface AssessAllProgress {
  running: boolean;
  total: number;
  done: number;
  current: string | null;
  errors: { student: string; error: string }[];
  reason?: string;
}

export type SmartDropResult =
  | ({ kind: "module_import" } & UploadResult & { module_name: string })
  | { kind: "document_summary"; summary: string; files_processed: number; usage: { tokens_prompt: number; tokens_completion: number } };

export const api = {
  cohorts: () => req<Cohort[]>("/cohorts"),
  modules: (cohortId: number) => req<ModuleSummary[]>(`/cohorts/${cohortId}/modules`),
  renameCohort: (cohortId: number, name: string) =>
    req<Cohort>(`/cohorts/${cohortId}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteCohort: (cohortId: number) => req<{ deleted: boolean }>(`/cohorts/${cohortId}`, { method: "DELETE" }),
  renameModule: (moduleId: number, name: string) =>
    req<ModuleSummary>(`/modules/${moduleId}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteModule: (moduleId: number) =>
    req<{ deleted: boolean; orphaned_students_removed: number }>(`/modules/${moduleId}`, { method: "DELETE" }),
  module: (moduleId: number) => req<{ id: number; name: string; case_study_html: string }>(`/modules/${moduleId}`),
  rubric: (moduleId: number) => req<RubricTrait[]>(`/modules/${moduleId}/rubric`),
  students: (moduleId: number) => req<StudentSummary[]>(`/modules/${moduleId}/students`),
  submissions: (studentId: number, moduleId: number) =>
    req<SubmissionFile[]>(`/students/${studentId}/submissions?module_id=${moduleId}`),
  reviews: (studentId: number, moduleId: number) =>
    req<ReviewsResponse>(`/reviews?student_id=${studentId}&module_id=${moduleId}`),
  saveReviews: (
    studentId: number,
    moduleId: number,
    payload: { framing_note: string | null; traits: { trait_id: number; level: number; comment: string | null; source: string }[] },
  ) =>
    req<ReviewSummary>(`/reviews?student_id=${studentId}&module_id=${moduleId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  aiAssist: (studentId: number, moduleId: number) =>
    req<AiAssistResponse>("/ai-assist", {
      method: "POST",
      body: JSON.stringify({ student_id: studentId, module_id: moduleId }),
    }),
  chatHistory: (studentId: number, moduleId: number) =>
    req<ChatMessage[]>(`/ai-assist/chat?student_id=${studentId}&module_id=${moduleId}`),
  sendChat: (studentId: number, moduleId: number, message: string) =>
    req<{ reply: string; trace: TraceStep[] }>("/ai-assist/chat", {
      method: "POST",
      body: JSON.stringify({ student_id: studentId, module_id: moduleId, message }),
    }),
  sendChatStream: (studentId: number, moduleId: number, message: string, onEvent: (e: StreamEvent) => void) =>
    streamSSE("/ai-assist/chat/stream", { student_id: studentId, module_id: moduleId, message }, onEvent),
  statistics: (moduleId: number) => req<ModuleStatistics>(`/modules/${moduleId}/statistics`),
  cohortOverview: (cohortId: number) => req<CohortOverview>(`/cohorts/${cohortId}/overview`),
  studentProfile: (studentId: number) => req<StudentProfile>(`/students/${studentId}/profile`),
  aiUsage: (studentId: number, moduleId: number) =>
    req<AiUsageAssessment>(`/ai-usage?student_id=${studentId}&module_id=${moduleId}`),
  assessAiUsage: (studentId: number, moduleId: number) =>
    req<AiUsageAssessment>("/ai-usage/assess", {
      method: "POST",
      body: JSON.stringify({ student_id: studentId, module_id: moduleId }),
    }),
  assistantHistory: (cohortId: number) => req<ChatMessage[]>(`/assistant/chat?cohort_id=${cohortId}`),
  assistantSend: (cohortId: number, message: string) =>
    req<{ reply: string; trace: TraceStep[]; student_id: number | null }>("/assistant/chat", {
      method: "POST",
      body: JSON.stringify({ cohort_id: cohortId, message }),
    }),
  assistantSendStream: (cohortId: number, message: string, onEvent: (e: StreamEvent) => void) =>
    streamSSE("/assistant/chat/stream", { cohort_id: cohortId, message }, onEvent),
  dossier: (studentId: number, moduleId: number) =>
    req<Dossier | null>(`/dossier?student_id=${studentId}&module_id=${moduleId}`),
  reportDownloadUrl: (studentId: number, moduleId: number, format: "docx" | "pdf") =>
    `${BASE}/students/${studentId}/report/download?module_id=${moduleId}&format=${format}`,
  gradebookDownloadUrl: (moduleId: number) => `${BASE}/modules/${moduleId}/gradebook.xlsx`,
  allReportsDownloadUrl: (moduleId: number, format: "docx" | "pdf") =>
    `${BASE}/modules/${moduleId}/reports.zip?format=${format}`,
  uploadModule: async (file: File, cohortName: string, moduleName: string): Promise<UploadResult> => {
    const form = new FormData();
    form.append("file", file);
    form.append("cohort_name", cohortName);
    form.append("module_name", moduleName);
    const res = await fetch(`${BASE}/uploads/module`, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail ?? `Upload failed: ${res.status}`);
    }
    return res.json();
  },
  suggestModuleName: async (file: File): Promise<string> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/uploads/suggest-module-name`, { method: "POST", body: form });
    if (!res.ok) return "";
    const data = await res.json();
    return data.suggested_name ?? "";
  },
  startAssessAll: (moduleId: number) =>
    req<AssessAllProgress & { started: boolean }>(`/modules/${moduleId}/assess-all`, { method: "POST" }),
  assessAllStatus: (moduleId: number) => req<AssessAllProgress>(`/modules/${moduleId}/assess-all/status`),
  smartDropZip: async (file: File, cohortId: number): Promise<SmartDropResult> => {
    const form = new FormData();
    form.append("file", file);
    form.append("cohort_id", String(cohortId));
    const res = await fetch(`${BASE}/uploads/smart-drop`, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail ?? `Processing failed: ${res.status}`);
    }
    return res.json();
  },
};
