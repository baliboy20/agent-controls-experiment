# Hooks

`log_event.py` is wired to PreToolUse, PostToolUse, SubagentStop and Stop in each run's `.claude/settings.json`. The workspace builder copies it to `<workspace>/.hooks/`. Each line records the time, event, tool, input and response (clipped at 2,000 characters). Both runs are logged the same way.
