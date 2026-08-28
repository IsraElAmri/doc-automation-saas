# Project Guidelines & Governance

## 1. Safety & Operational Constraints
- **Destructive Operations**: Never execute schema-destroying or destructive operations (like dropping tables, databases, or mass-deleting records) without explicitly proposing it in an implementation plan and securing the user's explicit approval first.
- **Secrets Management**: Never commit plain-text passwords, JWT secrets, or Gemini API keys to version control. Always maintain `.env.example` as a template and keep `.env` ignored.
- **File Ingestion Bounds**: Enforce streaming byte-counting size limits (max 10MB) before completing file writes. Validate magic bytes via header verification (`validate_file_header`) prior to text processing.

## 2. Coding & Architectural Standards
- **Logging**: Use `structlog` for all log outputs. Avoid `print()` or basic `logging.basicConfig`.
- **Concurrency**: Offload synchronous CPU/IO blocking operations (OCR, Gemini API calls, magic byte checks) to threadpools via `run_in_threadpool`.
- **Database Access**: Ensure all database queries filter by `user_id` to maintain multi-tenant data isolation. Use explicit `CASCADE` constraints on relationships.

## 3. Testing & Hygiene
- Keep `uploads/` clean of test artifacts (only `.gitkeep` retained in Git).
- Ensure all automated unit and integration tests in `tests/` pass with zero failures before release.
