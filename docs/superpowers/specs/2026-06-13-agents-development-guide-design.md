# AGENTS.md Development Guide Design

## Goal

Create a repository-root `AGENTS.md` that gives Codex concise, project-specific
instructions for developing and validating the Hongguo local server.

## Audience

The guide is written for coding agents working anywhere in this monorepo. It
must be useful without duplicating the detailed operational documentation in
the root and service READMEs.

## Structure

The guide will cover:

1. Repository purpose and the boundaries between `api-server`,
   `signer-service`, and `hongguo-contracts`.
2. The supported toolchain and canonical `uv`, `pytest`, and Ruff commands.
3. Implementation conventions for routes, transport, parsers, configuration,
   shared contracts, and dependency assembly.
4. Test expectations, including focused tests, full offline verification, and
   opt-in live tests.
5. Security rules for session data, service tokens, signed request material,
   loopback binding, header allowlists, and Frida binaries.
6. Communication, documentation, and change-management expectations for Codex.
7. Git repository checks, worktree protection, and commit-message conventions.

## Key Rules

- Preserve service boundaries: the API service must not acquire device or
  Frida responsibilities, and the signer must not acquire business parsing.
- Build the final upstream URL, headers, and body before signing, and do not
  mutate signed material afterward.
- Keep Python Frida and Android `frida-server` pinned to the same version.
- Never commit or expose captured sessions, credentials, tokens, private
  request material, local binaries, or `.local` runtime state.
- Prefer deterministic unit and integration tests. Live tests remain disabled
  unless `HONGGUO_RUN_LIVE_TESTS=1` is explicitly set.
- Use Simplified Chinese for user communication, progress updates, questions,
  and final responses. Keep code identifiers, commands, paths, protocol fields,
  and established technical terms in their original form.
- Keep changes scoped, follow existing patterns, and update tests and
  documentation when behavior or interfaces change.
- Before Git operations, confirm the current directory belongs to a repository.
  Never claim a commit or push succeeded when no repository exists or the
  command failed.
- Inspect `git status` before committing. Separate agent changes from existing
  user changes, stage only intended files, and never discard unrelated work
  without explicit authorization.
- Write concise Chinese commit subjects using an appropriate conventional
  prefix: `feat`, `fix`, `style`, `docs`, or `refactor`. Use `test`, `chore`,
  or another established prefix when it describes the change more accurately.

## Verification

After writing `AGENTS.md`:

- Confirm all referenced paths and commands exist in the repository.
- Run `uv run ruff check .`.
- Run `uv run pytest -q`.
- Review the resulting diff for accidental secrets, duplicated README content,
  and instructions that conflict with the current codebase.

## Non-Goals

- Replacing service READMEs or troubleshooting documentation.
- Documenting every HTTP endpoint or environment variable.
- Enabling live tests or requiring a running emulator for normal validation.
- Changing source code, dependencies, runtime configuration, or architecture.
