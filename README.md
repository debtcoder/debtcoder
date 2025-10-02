# DebtCoder Ops Pack

Welcome to the dojo locker. This repo is the shareable slice of our infra stack—just the pieces we’re cool blasting to the world:

- `debtcodersdojo.com` + `debtcodersdoja.com` landing vibes
- FastAPI brain behind `api.debtcodersdoja.com`
- NGINX server blocks, runbooks, and the handoff playbook for friendly bots

## What’s in the crate?
```
web/
├── api.debtcodersdoja.com/    # FastAPI app, systemd units, deployment notes
├── nginx/                     # sites-available configs + enabled symlinks
└── www/                       # static microsites per domain

dashboard/                     # Vite + React Ops cockpit (build → dist/)

AGENT.md                       # ops runbook for humans
AGENTS.md                      # contributor + style guide
AI_AGENT_HANDOFF.md            # production briefing for automation homies
style.md                       # palette + theme cheatsheet
```
No secrets live here. `.gitignore` already walls off uploads, certs, logs, and anything spicy.

## Boot it up quick
```bash
git clone git@github.com:debtcoder/debtcoder.git
cd debtcoder
# pull fresh assets from the prod box when you’re ready to sync
rsync -av /home/debtcoder/web ./web/
rsync -av /home/debtcoder/dashboard ./dashboard/
cp /home/debtcoder/{AGENT.md,AGENTS.md,AI_AGENT_HANDOFF.md} ./
```

Before you push, skim `AGENT.md` so you don’t miss a deploy step. Need GitHub to listen? Remember: on the server we ride with
`sudo env GIT_SSH_COMMAND=... git push` so the network cops chill out.

### Dashboard dev flow
The React cockpit talks to `https://api.debtcodersdoja.com` by default. Point it elsewhere with `VITE_API_BASE`.

```
cd dashboard
npm install
npm run dev -- --host 0.0.0.0 --port 4173
# build static bundle
npm run build
```

Ship the compiled `dist/` via NGINX (e.g., `/var/www/api.debtcodersdoja.com/dashboard`) or any static host.

## Hit me up
Maintainer: debtCoder <debtcoder@gmail.com>
