@echo off
REM ============================================================================
REM  launch_fable5.bat
REM  Opens a NEW Git Bash window, cd's into the Research Engine project, and
REM  launches Claude Code as "fable 5" with bypass-permissions, seeded with the
REM  Track B kickoff context so it hits the ground running.
REM
REM  EDIT THESE IF NEEDED:
REM    MODEL    - the exact model id/alias for "fable 5" (space is fine, quoted).
REM               If Claude rejects it, set the correct model string here.
REM    GITBASH  - path to Git Bash (auto-falls back to bash.exe).
REM ============================================================================
setlocal

set "MODEL=fable 5"
set "PROJECT_WIN=C:\Users\Isaac\OneDrive\Desktop\beta\Research Engine"
set "PROJECT_BASH=/c/Users/Isaac/OneDrive/Desktop/beta/Research Engine"

set "GITBASH=C:\Program Files\Git\git-bash.exe"
if not exist "%GITBASH%" set "GITBASH=C:\Program Files\Git\bin\bash.exe"
if not exist "%GITBASH%" (
  echo Git Bash not found. Edit GITBASH in this .bat to your git-bash.exe path.
  pause
  exit /b 1
)

REM Seed prompt: keep it apostrophe-free so bash single-quoting stays simple.
set "SEED=You are fable 5 taking over the Research Engine project. First read docs/NEXT_SESSION_TRACKB.md in full, then the top section of HANDOFF.md and docs/architecture/benchmark.md. Then continue Track B: (Option 2) fix discovery relevance so sources are on-topic, then (Option 3) add in-pipeline citation grounding so FACT is above zero. Reproduce the baseline first with: research-engine bench --tasks 1 --judge ollama, read Research/benchmarks, then work TDD-first and re-measure with research-engine bench after each change. Keep mypy strict and ruff green. Branch feat/deepresearch-bench; update HANDOFF.md and refresh the PR at end of session."

start "fable 5 - Research Engine" "%GITBASH%" -c "cd '%PROJECT_BASH%' && claude --dangerously-skip-permissions --model '%MODEL%' '%SEED%'; exec bash"

endlocal
