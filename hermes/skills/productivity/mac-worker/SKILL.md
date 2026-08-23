# Mac Worker Delegation

Use this skill when Evgenii asks Hermes in Telegram to give Codex or Claude Code
a task on his Mac, or uses an explicit command-shaped phrase such as:

- `mac run codex personal-ai-os <task>`
- `mac run claude personal-ai-os <task>`
- `mac status <job_id>`
- `mac stop <job_id>`

Natural Russian phrases such as `передай Codex на моём Mac задачу ...` route to
the same tools.

## Required Routing

- Start work only with `mac_worker_run`.
- Use the configured project alias; never invent or pass a filesystem path.
- Default to `agent=codex` when Evgenii says Codex or does not name an agent.
- Use `agent=claude` only when he explicitly asks for Claude.
- Return the `job_id` and say that the task is running in the background.
- Use `mac_worker_status` for progress or completion and `mac_worker_stop` for a
  stop request.
- Use `mac_worker_doctor` for a connectivity/readiness check.

## Git Authorization

`allow_commit` and `allow_push` must remain false unless Evgenii explicitly asks
for that exact action in the current message. A request to fix, implement, test,
or finish work is not permission to commit or push. `allow_push=true` also
requires `allow_commit=true`.

## Safety Boundaries

- Do not use `terminal`, `execute_code`, or another shell tool as a fallback for
  Mac access.
- Do not place secrets, tokens, passwords, SSH material, or environment values
  in the task prompt.
- Do not claim success from a running job. Read status until it is terminal.
- If a project alias is rejected, ask Evgenii to add it to the server-owned
  allowlist; never retry with a raw path.
- If Claude is unavailable or unauthenticated, report that fact and offer Codex
  without changing the requested task.
