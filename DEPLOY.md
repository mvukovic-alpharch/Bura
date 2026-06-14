# BURA — Deployment Runbook (iPad / Termius native)

Soup to nuts. Every step is a command you run from Termius on the iPad.
The droplet does the always-on work; the iPad is the cockpit; Drive is
the filing cabinet. Total hands-on time ~2.5 hours, then it soaks.

> GATE REMINDER: this stands up the live poller. Per your own sequencing,
> provision only after (a) the ArchAlpha 15-call streak is complete and
> (b) ROTH OBA language on outside business / gambling is read and clear.
> Everything in `engine/` is offline research with no compliance surface
> and can be built/run anytime. The poller is the line.

---

## STAGE 1 — Provision (~45 min)

1. DO → Create Droplet:
   - General Purpose, 2 vCPU / 8 GB, Ubuntu 24.04 LTS
   - Region NYC3 (match archalpha-prod)
   - Hostname `bura-prod`
   - Add your SSH key; enable Backups (+20%)

2. DO → Create Managed Database:
   - PostgreSQL, Basic 1 GB, same region, DB name `bura`
   - Settings → Trusted Sources → add `bura-prod` only
   - Copy the connection string (you'll put it in .env)

3. Termius → add host `bura-prod` with your key. SSH in, then:
```bash
adduser bura && usermod -aG sudo bura
rsync --archive --chown=bura:bura ~/.ssh /home/bura
# log back in as bura from here on
ufw allow OpenSSH && ufw enable
apt update && apt upgrade -y
apt install -y python3.12 python3.12-venv python3-pip git postgresql-client
```

## STAGE 2 — Code (~30 min)

4. GitHub → new private repo `bura` under mvukovic-alpharch.
5. On droplet, dedicated deploy key (mirrors your id_deepm pattern):
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_bura -N ""
cat ~/.ssh/id_bura.pub   # paste into repo Deploy Keys (read/write)
cat >> ~/.ssh/config <<'EOF'
Host github-bura
  HostName github.com
  IdentityFile ~/.ssh/id_bura
  IdentitiesOnly yes
EOF
```
6. Clone + env:
```bash
cd ~ && git clone git@github-bura:mvukovic-alpharch/bura.git
cd bura && python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
mkdir -p logs
```
7. Secrets — `config/.env`, mode 600, NEVER committed:
```bash
cat > config/.env <<'EOF'
DB_URL=postgresql://USER:PASS@HOST:PORT/bura?sslmode=require
SGO_API_KEY=
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
DAILY_API_CALL_BUDGET=900
EOF
chmod 600 config/.env
```

## STAGE 3 — Database (~20 min)

8. Build schema + seed:
```bash
psql "$DB_URL" -f db/schema.sql
psql "$DB_URL" -f db/seed_leagues.sql
```
9. Smoke test the spine:
```bash
psql "$DB_URL" -c "SELECT league_key,sleeve FROM leagues ORDER BY sleeve;"
```

## STAGE 4 — Feed + first poll (~45 min, the real session)

10. Register at sportsgameodds.com (free tier). Put the key in `.env`.
11. **GO/NO-GO CHECK** — confirm the free tier actually carries the
    periphery leagues with draw + totals markets and Pinnacle present:
```bash
source venv/bin/activate
python -m services.poller periphery   # watch the printed summary
psql "$DB_URL" -c "SELECT l.name, COUNT(*) FROM odds_snapshots s
  JOIN markets m USING(market_id) JOIN leagues l USING(league_key)
  GROUP BY l.name ORDER BY 2 DESC;"
```
   - If HNL / Primera A return rows incl. draw+total → proceed.
   - If they don't → this is the $0 kill point. Either upgrade to the
     $99 tier ONLY if coverage appears there, or stop. Do not spend
     further on a feed that can't see the sleeve.
12. If `_parse_feed` returns 0 on a live event with known odds, adjust
    ONLY that function to the real JSON field paths (it's written to be
    the single adjustment point), then re-run. Everything downstream
    consumes normalized Quotes, so nothing else changes.

## STAGE 5 — Schedule + soak (3 weeks, ~0 effort)

13. `crontab -e` as user bura:
```
*/5  * * * *  /home/bura/bura/scripts/poll_benchmark.sh >> /home/bura/bura/logs/poll.log 2>&1
*/12 * * * *  /home/bura/bura/scripts/poll_periphery.sh >> /home/bura/bura/logs/poll.log 2>&1
*/30 * * * *  /home/bura/bura/scripts/close_capture.sh  >> /home/bura/bura/logs/close.log 2>&1
```
14. Telegram fires only on errors / budget breach. Silence = healthy.
    Check row counts twice a week, 5 minutes:
```bash
psql "$DB_URL" -c "SELECT COUNT(*) snaps,
  COUNT(DISTINCT market_id) mkts, MAX(ts) latest FROM odds_snapshots;"
```

## STAGE 6 — Calibration verdict (Week 4, one session)

15. Replace periphery priors with measured copy-lag + dispersion from
    real snapshots; recompute PeripheryScores.
16. Fit BP per soccer league (`engine.bp_soccer.fit_moments`) on current
    results; price draw/totals vs captured closes; start paper CLV log.
17. **THE GATE (unchanged):** CLV > 0, t-stat significant, ≥500 paper
    observations on the draw/totals surface.
    - PASS → consider funded live test + paid feed. PAPER_MODE stays
      True until you deliberately flip it.
    - FAIL → `doctl compute droplet delete bura-prod`. Total cost of
      finding out: ~2 months × ~$90. The cheap kill is the point.

## Google Drive (filing cabinet)

Nightly, drop the day's blotter + CLV summary into the Bura/ Drive
folder as plain files so you read numbers from the couch, no SSH.
(Wire this once the Drive connector is cooperating.)

---

### The stack, one line each
Termius = cockpit · bura-prod = engine · managed PG = spine ·
Claude Code = builder (runs on droplet) · Telegram = nervous system ·
Drive = filing cabinet · RunPod = later, only if a real model earns it.
