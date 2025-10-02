# Agent Runbook

## Context
- User: `debtcoder` (sudo group)
- Host: Ubuntu 24.04.3 LTS (workspace sandbox, live production server)
- Repository root: `/home/debtcoder`
- Goal: Serve landing pages for `debtcodersdojo.com`, `debtcodersdoja.com`, and run the FastAPI backend at `api.debtcodersdoja.com` behind NGINX with Let's Encrypt TLS.
- Reference `AI_AGENT_HANDOFF.md` for the production host briefing when delegating to another automation agent.

## Current State
- FastAPI service deployed under systemd as `api-debtcodersdoja.service` (proxied by NGINX on 443).
- Certificates issued and valid for all domains (check `certbot certificates`).
- GitHub repository `git@github.com:debtcoder/debtcoder.git` contains the curated infrastructure snapshot (branch `main`).
- Network egress for unprivileged commands is restricted; use `sudo` for outbound network operations (Git pushes, curl to external hosts, etc.).

```
web/
|── api.debtcodersdoja.com/
|   |── app/main.py
|   |── config/systemd/
|   |   |── api-debtcodersdoja.env.example
|   |   `── api-debtcodersdoja.service
|   |── data/MOTD.md
|   |── requirements.txt
|   `── uploads/.gitkeep
|── nginx/
|   |── sites-available/
|   |   |── api.debtcodersdoja.com
|   |   |── debtcodersdojo.com
|   |   `── debtcodersdoja.com
|   `── sites-enabled/
|       |── api.debtcodersdoja.com -> ../sites-available/api.debtcodersdoja.com
|       |── debtcodersdojo.com -> ../sites-available/debtcodersdojo.com
|       `── debtcodersdoja.com -> ../sites-available/debtcodersdoja.com
`── www/
    |── api.debtcodersdoja.com/index.html
    |── debtcodersdojo.com/index.html
    `── debtcodersdoja.com/index.html
```

## Files of Interest
- FastAPI backend: `/srv/api.debtcodersdoja.com/app/main.py`
- systemd unit/env: `/etc/systemd/system/api-debtcodersdoja.service`, `/etc/api-debtcodersdoja.env`
- NGINX configs: `/etc/nginx/sites-available/*.com`
- Repo handoff docs: `AI_AGENT_HANDOFF.md`, `AGENT.md`, `AGENTS.md`
- Git workspace for GitHub sync: `/home/debtcoder/debtcoder_repo`

## Deployment Checklist (Production)
1. **App updates**
   ```bash
   sudo systemctl stop api-debtcodersdoja.service
   rsync -av web/api.debtcodersdoja.com/ /srv/api.debtcodersdoja.com/
   sudo chown -R www-data:www-data /srv/api.debtcodersdoja.com
   sudo -u www-data /srv/api.debtcodersdoja.com/.venv/bin/pip install -r /srv/api.debtcodersdoja.com/requirements.txt
   sudo systemctl start api-debtcodersdoja.service
   sudo systemctl status api-debtcodersdoja.service
   ```
2. **NGINX changes**
   ```bash
   rsync -av web/nginx/sites-available/ /etc/nginx/sites-available/
   sudo nginx -t
   sudo systemctl reload nginx
   ```
3. **Certificates**
   ```bash
   sudo certbot renew --dry-run
   ```
4. **Smoke tests**
   ```bash
   curl -fsS https://api.debtcodersdoja.com/healthz
   curl -fsS https://api.debtcodersdoja.com/diagnostics
   curl -fsS https://api.debtcodersdoja.com/motd
   curl -fsS "https://api.debtcodersdoja.com/duckduckgo?q=openai"
   curl -fsS https://api.debtcodersdoja.com/uploads
   ```

## GitHub Sync
- Public repo: `git@github.com:debtcoder/debtcoder.git`
- Local workspace: `/home/debtcoder/debtcoder_repo`
- Push flow:
  ```bash
  cd /home/debtcoder/debtcoder_repo
  rsync -av --exclude='uploads' --exclude='.git' /home/debtcoder/web/ ./web/
  cp /home/debtcoder/AGENT.md /home/debtcoder/AGENTS.md /home/debtcoder/AI_AGENT_HANDOFF.md ./
  git status
  git add ...
  git commit -m "..."
  sudo env GIT_SSH_COMMAND="ssh -i /home/debtcoder/.ssh/id_ed25519 -o StrictHostKeyChecking=accept-new" git push
  ```

## Notes & Limitations
- Outbound network requires `sudo` due to seccomp restrictions.
- Upload endpoints accept arbitrary files; monitor `/srv/api.debtcodersdoja.com/uploads` for abuse.
- Always verify `AI_AGENT_HANDOFF.md` is current before sharing with external agents.

## Next Steps
- Add monitoring/alerts for the FastAPI service and NGINX logs.
- Automate GitHub sync via cron/systemd timer run under sudo if frequent pushes are expected.
