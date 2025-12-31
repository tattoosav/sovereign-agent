# RunPod SSH Key Setup Guide

## Step 1: Generate SSH Key on Windows

### Option A: Using PowerShell (Recommended)

Open PowerShell as Administrator and run:

```powershell
# Create .ssh directory if it doesn't exist
mkdir -Force $env:USERPROFILE\.ssh

# Generate SSH key pair
ssh-keygen -t ed25519 -C "runpod" -f $env:USERPROFILE\.ssh\runpod_key

# When prompted for passphrase, press Enter twice (no passphrase for ease of use)
```

This creates two files:
- `C:\Users\sinis\.ssh\runpod_key` - Private key (KEEP SECRET)
- `C:\Users\sinis\.ssh\runpod_key.pub` - Public key (upload to RunPod)

### Option B: Using Git Bash

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "runpod" -f ~/.ssh/runpod_key

# Press Enter twice for no passphrase
```

## Step 2: Get Your Public Key

### PowerShell:
```powershell
# Display your public key
Get-Content $env:USERPROFILE\.ssh\runpod_key.pub

# Or copy to clipboard
Get-Content $env:USERPROFILE\.ssh\runpod_key.pub | Set-Clipboard
```

### Git Bash:
```bash
cat ~/.ssh/runpod_key.pub
```

The output will look like:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... runpod
```

## Step 3: Add Public Key to RunPod

1. Go to [runpod.io](https://runpod.io) and log in
2. Click your **profile icon** (top right) → **Settings**
3. Go to **SSH Public Keys** section
4. Click **+ Add SSH Key**
5. Paste your public key (the entire line starting with `ssh-ed25519`)
6. Give it a name like "Windows-Main"
7. Click **Save**

## Step 4: Test SSH Connection

After deploying a pod:

```powershell
# Test connection (replace with your pod's info)
ssh -i $env:USERPROFILE\.ssh\runpod_key root@IP -p PORT
```

## Step 5: Configure Windows SSH

Create or edit `C:\Users\sinis\.ssh\config`:

```
Host runpod
    HostName YOUR_POD_IP
    Port YOUR_POD_PORT
    User root
    IdentityFile C:\Users\sinis\.ssh\runpod_key
    StrictHostKeyChecking no
```

Then connect simply with:
```powershell
ssh runpod
```

## Troubleshooting

### "Permission denied (publickey)"
- Make sure you added the PUBLIC key (.pub file) to RunPod
- Check key permissions: `icacls $env:USERPROFILE\.ssh\runpod_key /inheritance:r /grant:r "$env:USERNAME:R"`

### "Connection refused"
- Pod might still be starting (wait 30-60 seconds)
- Check if pod is running in RunPod dashboard

### "Host key verification failed"
- Add `-o StrictHostKeyChecking=no` to your ssh command
- Or remove old entry: `ssh-keygen -R [IP]:PORT`

## Quick Reference

| Item | Location |
|------|----------|
| Private Key | `C:\Users\sinis\.ssh\runpod_key` |
| Public Key | `C:\Users\sinis\.ssh\runpod_key.pub` |
| SSH Config | `C:\Users\sinis\.ssh\config` |

## Environment Variables

Set these for the deploy scripts:

```powershell
# PowerShell
$env:RUNPOD_KEY = "$env:USERPROFILE\.ssh\runpod_key"

# Or add to your PowerShell profile for persistence
Add-Content $PROFILE "`n`$env:RUNPOD_KEY = `"$env:USERPROFILE\.ssh\runpod_key`""
```

```cmd
# Command Prompt
set RUNPOD_KEY=%USERPROFILE%\.ssh\runpod_key
```
