# Working agreement

## Before changing code

- Read the files you are about to change. Never edit from memory of a filename.
- If the request is ambiguous in a way that changes the output, ask one question,
  then proceed.
- Do not add a dependency without saying so first.

## While writing

- Match the surrounding code — its naming, comment density and idioms. A patch
  should be invisible in review except for the behaviour change.
- Return new values rather than mutating arguments in place.
- Handle every error explicitly. Never swallow an exception.
- Validate anything arriving from a user, a file, or an API.
- Never hardcode a secret.
- Extract rather than let a file grow past ~400 lines.

## Verifying

- Run the code. Report the real output, including failures.
- If you did not verify something, say so.
- Diagnostics arrive after each edit inside a `<diagnostics>` tag. Treat them as
  authoritative and fix them before continuing; do not re-run a linter to confirm.
- Delegate implementation with the task tool when a subagent fits the work better;
  state what you delegated and what came back.

## Tool calls

- Inspect real files with your tools instead of guessing at contents.
- Put only the parameter value inside a tool call — never reasoning or commentary.
  Think first, then emit a clean call.

## Never

- Commit or push unless asked.
- Reformat files you were not asked to touch.
- Modify a test to make it pass. If a test looks wrong, say so and stop.
- Describe work as complete while part of it is unfinished — name what is left.
