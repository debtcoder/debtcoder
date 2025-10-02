# Repository Guidelines

## Project Structure & Module Organization
- `AGENT.md` captures the operational runbook; update it when infrastructure steps change.
- `AGENTS.md` (this document) should evolve as contributor processes mature.
- `web/nginx/sites-available/` holds per-domain server blocks; mirror changes into `sites-enabled/` via symlinks.
- `web/www/<domain>/index.html` stores static landing pages; add shared assets (fonts, images) under `web/www/shared/` if you introduce them.

## Build, Test, and Development Commands
- No build pipeline exists; HTML/CSS are served as-is.
- Preview a page locally: `python3 -m http.server --directory web/www/debtcodersdojo.com 8080`.
- Validate NGINX syntax before deployment: `nginx -t -c $(pwd)/web/nginx/nginx.conf` (create a temp wrapper config if needed).
- Sync staged assets to a server: `rsync -av web/www/ user@host:/var/www/`.

## Coding Style & Naming Conventions
- HTML and CSS use two-space indentation; keep inline CSS blocks alphabetized where practical.
- Prefer semantic HTML (`<main>`, `<section>`, `<footer>`) and accessible language (descriptive link text, high-contrast palettes).
- Keep filenames lowercase with hyphens, e.g., `launch-offer.html`.
- When adding CSS classes, follow a lightweight BEM-style pattern (`block__element--modifier`) to avoid collisions across landing pages.

## Testing Guidelines
- Manually load each domain in a browser or run `curl -I https://example` to confirm 200 responses and redirects.
- Use `npx htmlhint web/www/debtcodersdojo.com/index.html` before committing markup changes; add `.htmlhintrc` if project-wide rules emerge.
- After NGINX changes, run `sudo nginx -t` on the target host and monitor `/var/log/nginx/*.log` for regressions during rollout.

## Commit & Pull Request Guidelines
- Craft commits in the imperative mood with focused scope, e.g., `Add nginx block for dojo domain`.
- Reference related tickets or context tags in the commit body when available.
- Pull requests should summarize the change, list validation steps (commands run, logs inspected), and include screenshots for any visual updates.
- Request review from someone familiar with infra changes before merging configuration edits.

## Deployment & Configuration Tips
- Certificates are expected under `/etc/letsencrypt/live/<domain>/`; keep server blocks pointing to those canonical paths.
- Update DNS first, then run the Certbot commands documented in `AGENT.md` to avoid rate-limit retries.
- After deployment, schedule periodic `certbot renew --dry-run` checks and external monitoring for SSL expiry.

## Automation Handoffs
- When another AI or automation agent needs to operate on the live host, share `AI_AGENT_HANDOFF.md` so they receive the production context, sudo password, and verification targets upfront.
- Set the environment context block exactly as shown in that file (`approval_policy: never`, `sandbox_mode: danger-full-access`, `network_access: enabled`) to prevent unnecessary approval prompts.
