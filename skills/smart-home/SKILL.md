---
name: smart-home
description: "Use when working on the home automation hub - Homebridge, Apple Home/Casa, Nest cameras, the Midea AC, Fire TV, Kasa plugs, OctoPrint, the Safari camera kiosk or the Mac mini - including any change to it, a device that stopped responding, or a request to back up or restore the Mac mini. Triggers: 'no se ven las cámaras', 'cambió la IP del Fire TV', 'actualiza homebridge', 'agrega un accesorio a Casa', 'restaura mi mac mini', 'respalda la mac mini'."
---

# Smart home (Mac mini hub)

## Overview

All facts (hosts, IPs, devices, plugins, secrets handling, decisions) live in the
private repo **`oscarolar/smart-home`** (clone it on the workstation if missing;
the Mac mini keeps its clone at `~/smart-home`). This skill is the method; the repo
is the truth. Never work from memory.

**Core rule: a change to the house is not done until the backup is pushed.**

## Every task

1. `git pull` in the smart-home clone (`gh repo clone oscarolar/smart-home` if missing), read `AGENTS.md`,
   then `docs/inventory.md`, and the ADR/runbook that matches the task.
2. Do the work over SSH as `AGENTS.md` says (PATH export, `pkill -TERM -x homebridge`
   to restart, never `hb-service restart` over SSH).
3. Read logs and configs through a secrets filter (`grep -viE 'secret|token|key'`)
   or `mac-mini/homebridge/config.redacted.json`. Never print a raw config or log.
4. Update the repo: `docs/inventory.md` for any fact that changed (IP, version,
   device, reservation), an ADR only for a decision between real alternatives,
   a runbook for a new failure mode. Commit and push.
5. Back up the host: `ssh <mini> '~/smart-home/scripts/backup.sh'` and confirm the
   output says `pushed` or `no changes`.
6. Report the backup commit together with the result.

## Restore / verify

"Restore my Mac mini" → follow `docs/runbooks/restore-mac-mini.md` exactly:
human bootstrap, `scripts/restore.sh`, human runs the printed root command,
`scripts/restore.sh --verify` must print 0 differences. The backup already has
`persist/` (HomeKit pairing) and all tokens; do not re-pair accessories or
re-authorize Nest unless verify or the plugin proves the backup is stale.

## Red flags - stop

| Thought | Reality |
|---|---|
| "The user is in a hurry / said *solo eso*" | Backup takes one command. Skipping it leaves the repo wrong for the next restore. |
| "The log shows it working, done" | Done = working + inventory updated + backup pushed. |
| "Nightly backup will catch it" | The nightly job is a safety net. Inventory/ADR updates never happen by themselves. |
| "I'll just tail the log" | The log contains OAuth secrets. Filter it. |
| "Ask the user whether they have backups" | The repo is the backup. Read it first. |
| "Re-pair everything in Casa after a restore" | `persist/` is in the backup; restore it. |

## Maintaining this skill

A new trap or procedure → a runbook in the repo, not here, unless it changes the
method above.
