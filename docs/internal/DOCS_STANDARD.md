# Internal Documentation Standard

## 1. Goal
Keep internal docs clear, searchable, and safe for collaboration.

## 2. Directory Rules
- `docs/releases/`: release-facing documents that should be tracked.
- `docs/internal/`: internal process documents that should be tracked.
- `docs/internal/private/`: temporary or sensitive internal notes (must stay gitignored).

## 3. Naming Rules
- Use upper snake case for major process docs:
  - `DOCS_STANDARD.md`
  - `ARCH_DECISION_YYYYMMDD_TOPIC.md`
- Use versioned names for release docs:
  - `RELEASE_PLAN_0.2.0.md`
  - `RELEASE_NOTES_0.2.0.md`

## 4. Required Sections
For plans and process docs, include these sections in order:
1. Context
2. Scope
3. Decision or Plan
4. Acceptance Criteria
5. Risks and Rollback
6. Owner and Date

## 5. Writing Rules
- One document should answer one main question.
- Prefer checklist items that are executable and verifiable.
- Include command examples when the action is operational.
- Keep language direct; avoid ambiguous wording.

## 6. Privacy and Safety
- Do not commit secrets, tokens, private endpoints, or personal data.
- If a note contains sensitive context, move it to `docs/internal/private/`.
- If a tracked doc references private data, replace values with placeholders.

## 6.1 Path Representation Rule
- Default project (repository itself) should use `.` as path.
- External project paths may be absolute internally for reliable metric collection.
- In docs and API responses, external absolute paths must be masked.
- Do not use `..` parent traversal in project path conventions.

## 7. Change Control
- For release-related docs, update them in the same PR as code changes.
- If behavior changes, update plan/notes/checklist together.
- Stale docs should be fixed or removed within the same release cycle.
