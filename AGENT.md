# Agent Runbook

## Context
- User: `debtcoder` (sudo group)
- Host: Ubuntu 24.04.3 LTS (workspace sandbox, no direct internet access)
- Repository root: `/home/debtcoder`
- Goal: Serve landing pages for `debtcodersdojo.com`, `debtcodersdoja.com`, and run the FastAPI backend at `api.debtcodersdoja.com` behind NGINX with Let's Encrypt TLS.
- Reference `AI_AGENT_HANDOFF.md` for the production host briefing when delegating to another automation agent.

## Current State
- NGINX: not installed (`nginx` not found) in this sandbox.
- Certbot: not installed (`certbot` not found) in this sandbox.
- FastAPI service scaffolding lives under `web/api.debtcodersdoja.com/` with systemd + env templates.
- Network egress blocked in this environment, so app dependencies and live certificate issuance cannot be tested here.

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
- FastAPI backend:
  - `web/api.debtcodersdoja.com/app/main.py`
  - `web/api.debtcodersdoja.com/requirements.txt`
  - `web/api.debtcodersdoja.com/config/systemd/api-debtcodersdoja.service`
  - `web/api.debtcodersdoja.com/config/systemd/api-debtcodersdoja.env.example`
  - `web/api.debtcodersdoja.com/data/MOTD.md`
- NGINX server blocks:
  - `web/nginx/sites-available/api.debtcodersdoja.com`
  - `web/nginx/sites-available/debtcodersdojo.com`
  - `web/nginx/sites-available/debtcodersdoja.com`
- Static landing pages:
  - `web/www/api.debtcodersdoja.com/index.html`
  - `web/www/debtcodersdojo.com/index.html`
  - `web/www/debtcodersdoja.com/index.html`

## Deployment Checklist (run on the production host)
1. **Install packages**
   ```bash
   sudo apt update
   sudo apt install nginx certbot python3-certbot-nginx python3-venv
   ```
2. **Sync repo assets**
   ```bash
   sudo mkdir -p /var/www/{api.debtcodersdoja.com,debtcodersdojo.com,debtcodersdoja.com}
   sudo mkdir -p /srv/api.debtcodersdoja.com
   sudo rsync -av web/www/ /var/www/
   sudo rsync -av web/api.debtcodersdoja.com/ /srv/api.debtcodersdoja.com/
   sudo chown -R www-data:www-data /var/www/api.debtcodersdoja.com
   sudo chown -R www-data:www-data /srv/api.debtcodersdoja.com
   ```
3. **Provision FastAPI runtime**
   ```bash
   sudo -u www-data python3 -m venv /srv/api.debtcodersdoja.com/.venv
   sudo -u www-data /srv/api.debtcodersdoja.com/.venv/bin/pip install -r /srv/api.debtcodersdoja.com/requirements.txt
   sudo cp /srv/api.debtcodersdoja.com/config/systemd/api-debtcodersdoja.env.example /etc/api-debtcodersdoja.env
   sudo chown root:www-data /etc/api-debtcodersdoja.env
   sudo chmod 640 /etc/api-debtcodersdoja.env
   ```
   - Edit `/etc/api-debtcodersdoja.env` if overriding data/upload paths or version tag.
4. **Install and start systemd service**
   ```bash
   sudo cp /srv/api.debtcodersdoja.com/config/systemd/api-debtcodersdoja.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now api-debtcodersdoja.service
   sudo systemctl status api-debtcodersdoja.service
   ```
5. **Configure NGINX**
   ```bash
   sudo rsync -av web/nginx/sites-available/ /etc/nginx/sites-available/
   sudo ln -sfn /etc/nginx/sites-available/api.debtcodersdoja.com /etc/nginx/sites-enabled/api.debtcodersdoja.com
   sudo ln -sfn /etc/nginx/sites-available/debtcodersdojo.com /etc/nginx/sites-enabled/debtcodersdojo.com
   sudo ln -sfn /etc/nginx/sites-available/debtcodersdoja.com /etc/nginx/sites-enabled/debtcodersdoja.com
   sudo nginx -t
   sudo systemctl reload nginx
   ```
6. **Issue certificates** (requires DNS pointing at this host)
   ```bash
   sudo certbot --nginx -d api.debtcodersdoja.com
   sudo certbot --nginx -d debtcodersdojo.com -d www.debtcodersdojo.com
   sudo certbot --nginx -d debtcodersdoja.com -d www.debtcodersdoja.com
   ```
   - Allow Certbot to configure HTTPS redirects.
7. **Smoke tests**
   ```bash
   curl -fsS https://api.debtcodersdoja.com/healthz
   curl -fsS https://api.debtcodersdoja.com/diagnostics | jq
   curl -fsS https://api.debtcodersdoja.com/motd
   curl -fsS "https://api.debtcodersdoja.com/duckduckgo?q=openai" | jq '.results[0]'
   ```
   - Upload a test file: `curl -F "files=@README.md" https://api.debtcodersdoja.com/upload`
   - Confirm Swagger UI renders at `https://api.debtcodersdoja.com/docs`.

## Notes & Limitations
- Sandbox lacks outbound internet and sudo privileges, so pip installs, NGINX reloads, and cert issuance must happen on the real server.
- `api-debtcodersdoja.service` expects the app under `/srv/api.debtcodersdoja.com` and runs as `www-data`; adjust if using a dedicated service account.
- Upload endpoints write directly to `API_UPLOAD_DIR`; monitor disk usage and consider quotas before exposing publicly.

## Next Steps
- Provision/open firewall ports 80 and 443 on the production host.
- Configure DNS A/AAAA records for all domains to the server IP.
- After deployment, add monitoring for systemd service health, SSL expiry, and disk usage of the upload directory.
