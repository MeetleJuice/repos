# Reusable Foundry task frame

This describes the controller's existing contract; it does not replace approved proposal data or the versioned model schemas.

## Goal
Implement the current approved task's declared outcome only.

## Context
Use the task packet, earlier saved interfaces and the complete supplied file values. The focused-context manifest lists omitted files. Request bounded source retrieval when a required file is absent; never invent its contents.

## Constraints
Change only approved task files. Preserve frozen tests, acceptance checks and controller-owned artifacts. No hidden scope expansion, placeholder files or claims that unexecuted tests passed. A model response cannot approve execution or an update.

## Done when
Return scoped complete files or exact edits. If already implemented, return exact current-source citations through the existing structured source-evidence response. The controller rechecks task/plan/source consistency before advancing; actual automated and manual checks determine behavioral acceptance.
