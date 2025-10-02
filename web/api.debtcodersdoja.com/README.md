# Debt Coders Doja API

FastAPI service powering `api.debtcodersdoja.com`. Provides:
- Plain-text MOTD feed sourced from `data/MOTD.md`
- Diagnostics + health endpoints for the GPT integration
- DuckDuckGo proxy endpoint (`/duckduckgo?q=`)
- File drop zone under `/upload` with list/fetch/delete helpers
- Auto-generated OpenAPI 3.1 schema and Swagger UI at `/docs`

## Layout
```
web/api.debtcodersdoja.com/
├── app/
│   └── main.py
├── config/
│   └── systemd/
│       ├── api-debtcodersdoja.env.example
│       └── api-debtcodersdoja.service
├── data/
│   └── MOTD.md
├── requirements.txt
└── uploads/
    └── .gitkeep
```

## Local development
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export API_PUBLIC_URL="http://127.0.0.1:9102"
export API_DATA_DIR="$(pwd)/data"
export API_UPLOAD_DIR="$(pwd)/uploads"
uvicorn app.main:app --reload --port 9102
```

Visit `http://127.0.0.1:9102/docs` for Swagger UI.

## Server deployment (systemd)
1. Copy repo contents to `/srv/api.debtcodersdoja.com`.
2. Create runtime dirs and ownership:
   ```bash
   sudo mkdir -p /srv/api.debtcodersdoja.com/{app,data,uploads}
   sudo rsync -av web/api.debtcodersdoja.com/ /srv/api.debtcodersdoja.com/
   sudo chown -R www-data:www-data /srv/api.debtcodersdoja.com
   ```
3. Create Python environment:
   ```bash
   sudo -u www-data python3 -m venv /srv/api.debtcodersdoja.com/.venv
   sudo -u www-data /srv/api.debtcodersdoja.com/.venv/bin/pip install -r /srv/api.debtcodersdoja.com/requirements.txt
   ```
4. Copy environment template and edit as needed:
   ```bash
   sudo cp /srv/api.debtcodersdoja.com/config/systemd/api-debtcodersdoja.env.example /etc/api-debtcodersdoja.env
   sudo chown root:root /etc/api-debtcodersdoja.env
   sudo chmod 640 /etc/api-debtcodersdoja.env
   ```
5. Install systemd unit:
   ```bash
   sudo cp /srv/api.debtcodersdoja.com/config/systemd/api-debtcodersdoja.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now api-debtcodersdoja.service
   ```
6. Verify:
   ```bash
   sudo systemctl status api-debtcodersdoja.service
   curl -fsS https://api.debtcodersdoja.com/healthz
   curl -fsS https://api.debtcodersdoja.com/diagnostics
   ```

Update `web/nginx/sites-available/api.debtcodersdoja.com` on the host, reload NGINX, and run Certbot per `AGENT.md` once the app service is healthy.
