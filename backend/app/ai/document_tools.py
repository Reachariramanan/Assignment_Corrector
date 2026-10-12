"""Read-only, DB-backed document-access tools shared by the Research and Review
agents. Each tool is bound via closure to one (student_id, module_id) - the agent
can only ever list/read that student's own already-ingested submission files
(never an arbitrary path, never another student's files), so there is no
injection surface even though the underlying content is student-supplied."""

from yukta import Tool, ToolParameter, ToolProcessor, ToolType

from app.db import db_cursor

# Largest real combined-submission doc observed so far is ~28k chars; this leaves
# comfortable headroom while still bounding a single tool-call's token cost. For
# anything longer, the agent can page through with the offset parameter.
READ_CHAR_LIMIT = 40000


def make_document_tools(student_id: int, module_id: int) -> ToolProcessor:
    def list_files() -> dict:
        with db_cursor() as cur:
            cur.execute(
                "SELECT id, kind, original_filename, source_format, length(extracted_text) AS chars "
                "FROM submission_files WHERE student_id = ? AND module_id = ? ORDER BY kind",
                (student_id, module_id),
            )
            return {"files": [dict(r) for r in cur.fetchall()]}

    def read_file(file_id: int, offset: int = 0) -> dict:
        with db_cursor() as cur:
            cur.execute(
                "SELECT original_filename, kind, extracted_text FROM submission_files "
                "WHERE id = ? AND student_id = ? AND module_id = ?",
                (file_id, student_id, module_id),
            )
            row = cur.fetchone()
            if not row:
                return {"error": f"No file with id {file_id} for this student"}
            text = row["extracted_text"] or ""
            chunk = text[offset : offset + READ_CHAR_LIMIT]
            remaining = max(0, len(text) - (offset + len(chunk)))
            return {
                "filename": row["original_filename"],
                "kind": row["kind"],
                "content": chunk,
                "chars_remaining_after_this_chunk": remaining,
                "next_offset": offset + len(chunk) if remaining else None,
            }

    processor = ToolProcessor()
    processor.add_tool(
        Tool(
            name="list_files",
            description="List this student's submitted files for this module (id, kind, filename, format, length).",
            parameters=[],
            tool_type=ToolType.CUSTOM,
            function=list_files,
        )
    )
    processor.add_tool(
        Tool(
            name="read_file",
            description=(
                "Read the extracted text content of one of this student's files, by its id from list_files. "
                "Returns up to 40,000 characters; if 'chars_remaining_after_this_chunk' is > 0, call again "
                "with offset='next_offset' to continue reading the rest."
            ),
            parameters=[
                ToolParameter(name="file_id", type="integer", description="File id from list_files", required=True),
                ToolParameter(name="offset", type="integer", description="Character offset to start reading from (for paging through a long file)", required=False, default=0),
            ],
            tool_type=ToolType.CUSTOM,
            function=read_file,
        )
    )
    return processor
