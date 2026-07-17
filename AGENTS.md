# AGENTS.md

> Guidelines for AI coding agents working in codebase.

---

## RULE 0 - THE FUNDAMENTAL OVERRIDE PREROGATIVE

If I tell you to do something, even if it goes against what follows below, YOU MUST LISTEN TO ME. I AM IN CHARGE, NOT YOU.

---

## RULE NUMBER 1: NO FILE DELETION

**YOU ARE NEVER ALLOWED TO DELETE A FILE WITHOUT EXPRESS PERMISSION.** Even a new file that you yourself created, such as a test code file. You have a horrible track record of deleting critically important files or otherwise throwing away tons of expensive work. As a result, you have permanently lost any and all rights to determine that a file or folder should be deleted.

**YOU MUST ALWAYS ASK AND RECEIVE CLEAR, WRITTEN PERMISSION BEFORE EVER DELETING A FILE OR FOLDER OF ANY KIND.**

---

## Irreversible Git & Filesystem Actions — DO NOT EVER BREAK GLASS

1. **Absolutely forbidden commands:** `git reset --hard`, `git clean -fd`, `rm -rf`, or any command that can delete or overwrite code/data must never be run unless the user explicitly provides the exact command and states, in the same message, that they understand and want the irreversible consequences.
2. **No guessing:** If there is any uncertainty about what a command might delete or overwrite, stop immediately and ask the user for specific approval. "I think it's safe" is never acceptable.
3. **Safer alternatives first:** When cleanup or rollbacks are needed, request permission to use non-destructive options (`git status`, `git diff`, `git stash`, copying to backups) before ever considering a destructive command.
4. **Mandatory explicit plan:** Even after explicit user authorization, restate the command verbatim, list exactly what will be affected, and wait for a confirmation that your understanding is correct. Only then may you execute it—if anything remains ambiguous, refuse and escalate.
5. **Document the confirmation:** When running any approved destructive command, record (in the session notes / final response) the exact user text that authorized it, the command actually run, and the execution time. If that record is absent, the operation did not happen.


### Code Editing Discipline

- Do **not** run scripts that bulk-modify code (codemods, invented one-off scripts, giant `sed`/regex refactors).
- Large mechanical changes: break into smaller, explicit edits and review diffs.
- Subtle/complex changes: edit by hand, file-by-file, with careful reasoning.

---

### Backwards Compatibility & File Sprawl

We optimize for a clean architecture now, not backwards compatibility.

- No "compat shims" or "v2" file clones.
- When changing behavior, migrate callers and remove old code **inside the same file**.
- New files are only for genuinely new domains that don't fit existing modules.
- The bar for adding files is very high.

---

### Logging & Console Output

- Use the **rich** library for all console output (informative, detailed, colorful).
- Prefer structured logging via Python's `logging` module over raw `print()`.
- No random print statements in library code; if needed, make them dev-only and clean them up.
- Log structured context: IDs, step numbers, metrics, etc.
- If a logger helper exists (e.g., in `common.py`), you must use it; do not invent a different pattern.

---

## Markdown Rules

**CRITICAL:** After creating or editing any Markdown file (`.md`), you MUST lint it with **pymarkdownlnt** before considering the work done:

| Tool | Command | Note |
|---|---|---|
| uv | `uv run pymarkdownlnt scan path/to/file.md` | Scan a specific file |
| uv | `uv run pymarkdownlnt scan docs/` | Scan all markdown files in a directory |
| uv | `uv run pymarkdownlnt fix path/to/file.md` | Fix auto-fixable violations in-place |
| conda / venv | `pymarkdownlnt scan path/to/file.md` | Scan a specific file — activate env first |
| conda / venv | `pymarkdownlnt scan docs/` | Scan all markdown files in a directory — activate env first |
| conda / venv | `pymarkdownlnt fix path/to/file.md` | Fix auto-fixable violations in-place — activate env first |

- Run pymarkdownlnt scan on **every** `.md` file you create or modify.
- If violations are reported, **fix them all** before committing.
- This applies to all markdown: documentation, specs, plans, READMEs, bead plans, etc.
- Treat pymarkdownlnt violations the same way you treat ruff/ty errors for Python — they are **blockers**, not suggestions.
