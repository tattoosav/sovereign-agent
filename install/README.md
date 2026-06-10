# Sovereign Agent + CRM — Offline Install

This USB contains a complete, self-contained, **offline** AI + CRM for one Windows
computer. It needs **no internet** at any point.

---

## Install (on the offline computer)

1. Copy this whole folder onto the computer (or run it straight from the USB).
2. Double-click **`INSTALL.bat`**.
3. Click **Yes** when Windows asks for administrator permission.
4. Wait. It takes several minutes (copying the AI models is the slow part).
5. When it says **INSTALL COMPLETE**, you're done.

That's it. The AI and CRM now start automatically every time the computer boots.

---

## Use it

- **CRM (main app):** open a browser to **http://127.0.0.1:8000/crm**
  Dashboard, Contacts, Pipeline, Follow-ups, and a "Backup now" button.
- **AI chat:** **http://127.0.0.1:8000/** — ask in plain English, e.g.
  *"add a contact named Maria, phone 555-0102"*, *"what follow-ups are due?"*

The full operator guide is in **`docs\AIRGAP_RUNBOOK.md`**.

---

## Good to know

- **100% offline.** It refuses to start if it ever detects an internet connection.
- **Your data stays on this machine only.** The CRM database is at
  `C:\Sovereign\workspace\.sovereign\crm.db`. A daily backup is written to
  `C:\Sovereign\workspace\.sovereign\backups\`.
  **Copy that backups folder to a second USB now and then — if this disk dies and you
  have no copy, the data is gone.**
- **Something wrong?** The installer writes a full log to `C:\Sovereign\logs\`.
  To remove everything, run `uninstall_airgap.ps1`.

---

## For the technician who built this USB

Build the bundle on an internet-connected Windows machine with Ollama installed:

```powershell
powershell -ExecutionPolicy Bypass -File install\build_bundle.ps1
```

It auto-downloads Python, Ollama, NSSM, the Python wheels, and the AI models, then
writes `checksums.txt`. Copy the resulting `SovereignAgent-USB` folder to the stick.
