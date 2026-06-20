# Hermes WebUI Runbook

Status label: supporting

Use this to open the existing WSL Hermes agent in `nesquena/hermes-webui` for local MOSS work.

## Start

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-hermes-webui.ps1 start
```

Then open `http://127.0.0.1:8787`.

The launcher keeps WebUI state under `/home/hermes/.hermes-moss/webui`, uses the Hermes agent checkout at `/home/hermes/hermes-agent`, and opens this repository as the default workspace.

## Manage

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-hermes-webui.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-hermes-webui.ps1 logs
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-hermes-webui.ps1 restart
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-hermes-webui.ps1 stop
```

The WebUI is separate from MOSS `POST /api/agent/query`. To route MOSS API queries to Hermes, keep using `scripts/dev-agent-api.ps1`.
