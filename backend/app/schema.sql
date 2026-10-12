PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cohorts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cohort_id INTEGER NOT NULL REFERENCES cohorts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    case_study_path TEXT,
    case_study_html TEXT,
    sample_answer_path TEXT,
    briefing_json TEXT,
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(cohort_id, name)
);

CREATE TABLE IF NOT EXISTS rubric_traits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    weight_pct REAL NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(module_id, name)
);

CREATE TABLE IF NOT EXISTS rubric_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trait_id INTEGER NOT NULL REFERENCES rubric_traits(id) ON DELETE CASCADE,
    level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 4),
    label TEXT NOT NULL,
    descriptor TEXT NOT NULL,
    UNIQUE(trait_id, level)
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cohort_id INTEGER NOT NULL REFERENCES cohorts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    moodle_participant_id TEXT,
    UNIQUE(cohort_id, name, moodle_participant_id)
);

CREATE TABLE IF NOT EXISTS submission_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'other',
    kind_source TEXT NOT NULL DEFAULT 'heuristic' CHECK (kind_source IN ('heuristic', 'ai')),
    original_filename TEXT NOT NULL,
    storage_path TEXT,
    object_key TEXT,
    source_format TEXT NOT NULL,
    extracted_html TEXT,
    extracted_text TEXT,
    UNIQUE(student_id, module_id, original_filename)
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    trait_id INTEGER NOT NULL REFERENCES rubric_traits(id) ON DELETE CASCADE,
    level INTEGER CHECK (level BETWEEN 1 AND 4),
    comment TEXT,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'ai_accepted')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, module_id, trait_id)
);

CREATE TABLE IF NOT EXISTS ai_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    trait_id INTEGER NOT NULL REFERENCES rubric_traits(id) ON DELETE CASCADE,
    suggested_level INTEGER CHECK (suggested_level BETWEEN 1 AND 4),
    rationale TEXT,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    yukta_session_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'assist' CHECK (kind IN ('assist', 'chat', 'briefing', 'research', 'review', 'grade', 'gap_analysis')),
    tokens_prompt INTEGER NOT NULL DEFAULT 0,
    tokens_completion INTEGER NOT NULL DEFAULT 0,
    iterations INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS research_dossiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    dossier_json TEXT NOT NULL,
    review_draft_json TEXT,
    files_read_count INTEGER NOT NULL DEFAULT 0,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, module_id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    trace_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_usage_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    has_declaration INTEGER NOT NULL DEFAULT 0,
    declared_tools TEXT,
    integration_quality TEXT,
    coaching_note TEXT,
    prompting_suggestions TEXT,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, module_id)
);

CREATE TABLE IF NOT EXISTS class_chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cohort_id INTEGER NOT NULL REFERENCES cohorts(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    trace_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gap_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    problem_solving_style TEXT,
    strengths_json TEXT,
    growth_areas_json TEXT,
    overall_narrative TEXT,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, module_id)
);

CREATE TABLE IF NOT EXISTS review_status (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    framing_note TEXT,
    total_weighted_score REAL,
    band TEXT,
    status TEXT NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'completed', 'not_submitted')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (student_id, module_id)
);
