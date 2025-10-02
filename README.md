# DebtCoder Infrastructure

This repository tracks public-facing infrastructure assets for the Debt Coders properties:
- Landing pages for `debtcodersdojo.com` and `debtcodersdoja.com`
- FastAPI backend powering `api.debtcodersdoja.com`
- NGINX server blocks and deployment runbooks

## Structure
Populate the repository by copying the curated files from the production workspace:

```
web/
├── api.debtcodersdoja.com/    # FastAPI app, systemd units, README
├── nginx/                     # Server blocks under sites-available/
└── www/                       # Static landing pages per domain

AGENT.md                       # Operations runbook
AGENTS.md                      # Contribution guidelines
AI_AGENT_HANDOFF.md            # Brief for automation agents
```

Avoid syncing credentials or runtime data (certificates, uploads, logs). The `.gitignore` already excludes common secrets and generated files.

## Fast Start
```bash
git clone git@github.com:debtcoder/debtcoder.git
cd debtcoder
# Copy in the desired directories/files from the production workspace
# e.g., rsync -av /home/debtcoder/web ./
```

Review `AGENT.md` for the deployment checklist before pushing changes.

## Contact
Maintainer: debtCoder <debtcoder@gmail.com>
