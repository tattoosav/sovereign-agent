# Sovereign Agent — Air-Gapped Operator Runbook

This machine runs a fully offline, autonomous AI coding agent. It is **never**
connected to the internet. Everything below is done on the box itself.

---

## 1. What it is

- A local AI agent (Ollama + Qwen 2.5 Coder) that runs **autonomously**.
- It watches a folder for work, does the work, saves the result, and keeps running
  unattended — surviving reboots.
- **Zero network.** The internet-capable tools have been removed from the software,
  outbound traffic is blocked by firewall, and a startup self-check aborts if it ever
  detects internet access.

Install layout (default `C:\Sovereign`):

```
C:\Sovereign\
  app\                 the agent software (+ .venv, config.yaml)
  workspace\
    tasks\
      inbox\           <-- you drop work here
      active\          task currently running
      done\            <-- finished work + <id>.result.md
      failed\          failed work + <id>.error.log
      state\           heartbeat.json (liveness)
  logs\                rotating logs (out.log, err.log, autonomous.log)
```

---

## 2. Submit work

Drop a file into `C:\Sovereign\workspace\tasks\inbox\`.

**Markdown task** — the whole file is the instruction. Filename = task id:

`inbox\add-logging.md`
```
Add structured logging to utils/parser.py and write a unit test for it.
```

**JSON task** — for an explicit id:

`inbox\job-42.json`
```json
{ "id": "job-42", "prompt": "Refactor the payment module into smaller functions." }
```

The agent picks up the oldest task automatically (within a few seconds), runs it to
completion, then moves on to the next.

---

## 3. Get results

- Completed: `tasks\done\<id>.result.md` — the agent's response, the model used,
  iteration count, and the files it created/modified. The original task file is moved
  into `done\` next to it.
- Failed: `tasks\failed\<id>.error.log` — what went wrong. The task is quarantined here
  so it never blocks the queue.

---

## 4. Check it's alive

- **Heartbeat:** open `tasks\state\heartbeat.json` — shows timestamp, process id, the
  task currently running, and counts. A recent timestamp = healthy.
- **Logs:** `logs\out.log` and `logs\autonomous.log` (rotating, capped — they never
  fill the disk).
- **Services:** open **Services** (services.msc) — `Ollama`, `SovereignAgent` (the
  autonomous loop), and `SovereignWeb` (the CRM web UI) should all be **Running**.

---

## 5. Verify there is no network (do this any time)

Run from an elevated PowerShell:

```powershell
# Built-in self-check: expect external internet = BLOCKED, Ollama = OK
& C:\Sovereign\app\.venv\Scripts\python.exe -m src.core.egress_guard

# Confirm the agent process talks ONLY to local Ollama (127.0.0.1:11434)
$pid = (Get-CimInstance Win32_Service -Filter "Name='SovereignAgent'").ProcessId
Get-NetTCPConnection -OwningProcess $pid | Select-Object RemoteAddress, RemotePort

# Confirm the outbound-block firewall rule is present
Get-NetFirewallRule -DisplayName "Sovereign-Block-Outbound-Python"
```

Any `RemoteAddress` other than `127.0.0.1`/`::1` would be unexpected — the build is
designed so this never happens.

---

## 6. Start / stop / restart

```powershell
Restart-Service SovereignWeb      # the CRM web UI
Restart-Service SovereignAgent    # the autonomous loop
Restart-Service Ollama            # the model backend
```

All three services auto-start at boot; `SovereignAgent` and `SovereignWeb` wait for
`Ollama` and auto-restart if they ever exit.

---

## 6a. The CRM

The CRM is the day-to-day tool. Two ways to use it:

- **Web UI:** browse to `http://127.0.0.1:8000/crm`. The web app runs automatically as
  the `SovereignWeb` service (starts at boot) — no need to launch anything. Tabs:
  Dashboard, Contacts, Pipeline, Follow-ups. The AI chat is at `http://127.0.0.1:8000/`.
- **Natural language:** in the AI chat, just say things like "add a contact named
  Maria, phone 555-0102", "log a call with contact 4 — wants a quote", "what
  follow-ups are due?", "show me the pipeline".

**Data & backups:** the customer database is `C:\Sovereign\workspace\.sovereign\crm.db`.
The autonomous daemon writes a **daily briefing** to `workspace\tasks\reports\` and a
**daily backup** (DB snapshot + CSV exports) to `workspace\.sovereign\backups\`. You
can also click **Backup now** in the CRM UI any time.

> IMPORTANT: this machine is air-gapped, so the customer database exists ONLY here.
> Periodically copy `workspace\.sovereign\backups\` to a second drive or USB. If this
> disk fails and you have no copy, the data is gone.

## 7. Add or replace models (offline)

Models live in `%USERPROFILE%\.ollama\models`. To add one, copy the exported model
blobs/manifests from a bundle into that folder (same way the installer did), then
`Restart-Service Ollama`. Verify with `ollama list`. Never run `ollama pull` — that
needs the internet and is not used by this build.

---

## 8. Uninstall

From the bundle: `powershell -ExecutionPolicy Bypass -File uninstall_airgap.ps1`
(add `-Purge` to also delete the workspace and results).

---

## 9. Troubleshooting

| Symptom | Check |
|---|---|
| Tasks not picked up | Is `SovereignAgent` running? Is disk space low (logs say "pausing intake")? |
| Task stuck | It is time-boxed; after the budget it is moved to `failed\` and the loop continues. |
| Agent won't start | Run the egress self-check — if the box can reach the internet, startup aborts by design. Disconnect the network. |
| Model errors | `ollama list` — confirm at least one `qwen2.5-coder` tag is installed. |
