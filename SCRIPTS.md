Migration & PR helper scripts

1) Move repo out of OneDrive (Windows PowerShell)

```powershell
# copy repository to safe path
mkdir C:\dev -ErrorAction Ignore
robocopy "C:\Users\Gabri\OneDrive\Documentos\easya-agenda" "C:\dev\easya-agenda" /MIR
```

2) Create branch, commit and push

```powershell
cd C:\dev\easya-agenda
git init
git remote add origin <your-remote-url>
git checkout -b rewrite/dashboard-v2-finalize
git add -A
git commit -m "dashboard-v2: ownership, historico, offline queue, frontend slug fixes"
git push -u origin rewrite/dashboard-v2-finalize
```

3) Open PR (gh CLI)

```powershell
gh pr create --title "dashboard-v2: ownership & historico" --body-file PR_NOTES.md --base main --head rewrite/dashboard-v2-finalize
```

## Ops / Monitoramento (produção)

Para subir um painel simples de containers + latência/uptime em produção (Portainer + Uptime Kuma), veja:

- deploy/ops/README.md
