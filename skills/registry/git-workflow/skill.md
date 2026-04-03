# Skill: Git Workflow

Usa questa skill per operazioni git con commit semantici e workflow pulito.

## Formato commit

```
<tipo>(<scope>): <descrizione breve>

[corpo opzionale]
```

Tipi:
- `feat`: nuova funzionalità
- `fix`: bug fix
- `docs`: documentazione
- `refactor`: refactoring senza cambio funzionalità
- `test`: aggiunta/modifica test
- `chore`: manutenzione (deps, config)

Esempi:
```
feat(agents): aggiungi supporto multi-cron per agente
fix(scheduler): correggi hot-reload su Windows
docs(readme): aggiorna istruzioni installazione
```

## Operazioni comuni

```bash
# Controlla stato
git status

# Aggiungi file specifici (mai git add .)
git add daemon/scheduler.py daemon/heartbeat.py

# Commit
git commit -m "feat(scheduler): aggiungi multi-cron per agente"

# Push
git push origin main
```

## Regole

- Mai `git add .` o `git add -A` — aggiungi file specifici
- Mai committare `.env` o file con secrets
- Un commit = una modifica logica
- Messaggi in italiano o inglese, mai misti nello stesso repo
- Branch feature: `feature/nome-feature`
- Branch fix: `fix/nome-bug`

## Permessi necessari

Richiede `bash: true` e comandi specifici nel cron.yaml:
```yaml
permissions:
  bash: true
# In agent_runner viene mappato a: Bash(git *)
```
