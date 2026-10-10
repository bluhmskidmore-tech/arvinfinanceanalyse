# Codex PRD Merged Bundle

Status label: archived/reference

This file is navigation only and is non-authorizing. It always defers to
`AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`.
If this file conflicts with that chain, follow the authority chain.

## Purpose

This directory is an archived/reference delivery bundle wrapper. It preserves a
historical Codex PRD handoff package and related copied documents. The wrapper
status applies to this bundled surface; it does not make any copied file inside
the bundle current repo authority.

## Authority Rule

- Current repo authority remains the root read path:
  `AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`.
- Files copied into this bundle may look authoritative, but they are reference
  copies unless the current root authority chain says otherwise.
- Do not use this bundle to override current metric definitions, execution
  boundaries, page contracts, or implementation priorities.

## Known Ghost References Inside This Bundle

Files copied into this bundle reference two documents that **never landed in this
repository**. They do not exist in the current checkout under any extension, and
`git ls-files` has no match:

- `docs/MOSS-V2 系统架构说明`
- `MOSS 系统：取值逻辑、计算层与规则总览`

Affected copies (left unmodified on purpose — this directory is a historical
snapshot, and rewriting the copies would destroy the record of what the original
handoff package claimed):

- `AGENTS.md`
- `docs/DOCUMENT_AUTHORITY.md`
- `docs/CODEX_HANDOFF.md`
- `docs/CODEX_KICKOFF_PROMPT.md`
- `docs/REPO_MERGE_GUIDE.md`

Do not search for these two documents, do not treat the reading orders inside the
bundle as complete, and do not use them to settle any conflict. Whether they get
written or formally retired is an owner decision. The authoritative note is the
"两个空置槽位（文件从未并入本仓库）" section of
[../DOCUMENT_AUTHORITY.md](../DOCUMENT_AUTHORITY.md), which also lists the
currently existing substitutes.

## Known Misleading Wording Inside This Bundle: 「鉴权」

Copies inside this bundle describe the API layer's duties as 「鉴权」. That term
conflates authentication with authorization and is **factually misleading about
this repository**. The live copies outside the bundle were corrected to 「授权」
on 2026-08-13; the bundle copies are left unmodified on purpose, for the same
snapshot-preservation reason given above.

Accurate current-state conclusion (verified 2026-08-13):

- Authorization **exists**: `backend/app/security/auth_context.py::ensure_user_allowed`
  performs `resource`/`action`/`scope` RBAC, wired into route dependencies via
  `backend/app/api/deps.py`.
- Authentication **does not exist**: no `HTTPBearer` / `OAuth2` / `APIKeyHeader` /
  JWT / session anywhere in the repo. Identity comes from `X-User-Id` /
  `X-User-Role` headers -> `MOSS_USER_ID` / `MOSS_USER_ROLE` env vars -> fallback
  constants `anonymous` / `viewer`, and is never verified.
- The trust switch `MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST` is **off by default**
  (headers ignored, all requests share one process-level identity); when on, any
  caller can claim any `user_id` / `role`. **Neither posture is authentication.**

Affected copies (left unmodified on purpose):

- `AGENTS.md` (line 42)
- `prd-moss-agent-analytics-os.md` (lines 49, 223)
- `docs/prd-moss-agent-analytics-os.md` (lines 49, 223)
- `docs/SYSTEM_STACK_SPEC_FOR_CODEX.md` (lines 11, 91)
- `docs/CODEX_HANDOFF.md` (line 28)
- `docs/CODEX_KICKOFF_PROMPT.md` (line 25)
- `docs/CACHE_SPEC.md` (line 8)

Do not read 「鉴权」 in these copies as evidence that the API layer verifies caller
identity, and do not build security judgements or external exposure on top of it.
The authoritative statement is the 「关键约束」 section of
[../../README.md](../../README.md) and section 1 of
[../SYSTEM_STACK_SPEC_FOR_CODEX.md](../SYSTEM_STACK_SPEC_FOR_CODEX.md).

## Use

- Use this bundle for historical context and migration/reference comparison.
- Prefer current root-level and `docs/` authority files for active work.
- If a bundled file conflicts with current repo docs, follow the current repo
  authority chain.
