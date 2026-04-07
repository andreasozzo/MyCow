# Skill: Git Workflow

Use this skill for git operations with semantic commits and a clean workflow.

## Commit format

```
<type>(<scope>): <short description>

[optional body]
```

Types:
- `feat`: new feature
- `fix`: bug fix
- `docs`: documentation
- `refactor`: refactoring without functional change
- `test`: add/modify tests
- `chore`: maintenance (deps, config)

Examples:
```
feat(agents): add multi-cron support per agent
fix(scheduler): fix hot-reload on Windows
docs(readme): update installation instructions
```

## Common operations

```bash
# Check status
git status

# Add specific files (never git add .)
git add daemon/scheduler.py daemon/heartbeat.py

# Commit
git commit -m "feat(scheduler): add multi-cron per agent"

# Push
git push origin main
```

## Rules

- Never `git add .` or `git add -A` — add specific files
- Never commit `.env` or files with secrets
- One commit = one logical change
- Messages in English, consistent throughout the repo
- Feature branch: `feature/feature-name`
- Fix branch: `fix/bug-name`

## Required permissions

Requires `bash: true` and specific commands in cron.yaml:
```yaml
permissions:
  bash: true
# In agent_runner this maps to: Bash(git *)
```
