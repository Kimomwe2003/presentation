# Backup Strategy

A deliberately simple, reliable PostgreSQL backup plan for a final-year project.
No enterprise tooling — just scheduled `pg_dump`, versioned dumps, and documented
restore. The two things that matter are **the database** (all accounts, orders,
wallet balances, transactions, chat, audit logs) and **uploaded media** (product
images in `media/`).

## What to back up

| Data | Where it lives | Why it matters |
|------|----------------|----------------|
| Database | `pgdata` volume (Docker) / your Postgres instance | Every record in the app |
| Media files | `media/` volume / `MEDIA_ROOT` | Product photos |

The backend code and migrations are already in version control (git) — they are
recoverable by cloning; they do not need "backing up".

## Strategy (simple, two-part)

1. **Database**: nightly `pg_dump` → gzipped `.sql.gz` files, kept for 7 days.
2. **Media**: nightly `rsync`/`tar` of the `media/` directory alongside the dumps.

Target a directory outside the Docker volumes (e.g. `/var/backups/reusehub`), and
optionally push a copy to any cheap remote (object storage, another box, or a USB
drive at demo time). For a final-year demo, local disk + the 7-day retention is
more than sufficient; the point is that restores actually work.

## Docker Compose: one-command backup

Because the DB runs in a container, the simplest reliable backup is:

```bash
docker compose exec db sh -c \
  'pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip' \
  > /var/backups/reusehub/$(date +%Y%m%d-%H%M%S).reusehub.sql.gz
```

### Sample backup script — `scripts/backup.sh`

```bash
#!/usr/bin/env bash
# Nightly backup for ReuseHub (Docker Compose). Edit DEST for your host.
set -euo pipefail

COMPOSE_DIR=/opt/reusehub
DEST=/var/backups/reusehub
KEEP_DAYS=7
mkdir -p "$DEST"

STAMP=$(date +%Y%m%d-%H%M%S)
cd "$COMPOSE_DIR"

# 1. Database
docker compose exec -T db \
  pg_dump -U "${POSTGRES_USER:-reusehub}" "${POSTGRES_DB:-reusehub}" | gzip \
  > "$DEST/$STAMP.reusehub.sql.gz"

# 2. Media (tar the volume contents via a temp container — simple, no deps)
docker run --rm -v reusehub_media:/media -v "$DEST:/backup" alpine \
  tar czf "/backup/$STAMP.media.tar.gz" -C /media .

# 3. Retention: prune dumps older than KEEP_DAYS
find "$DEST" -name '*.sql.gz' -mtime +"$KEEP_DAYS" -delete
find "$DEST" -name '*.media.tar.gz' -mtime +"$KEEP_DAYS" -delete

echo "Backup complete: $STAMP"
```

> Note: the volume name in `docker run` is `reusehub_media` when the Compose
> project directory is named `reusehub`; adjust it to match
> `docker volume ls` output on your host.

### Schedule it (cron)

```bash
# /etc/crontab or `crontab -e`
0 2 * * * /opt/reusehub/scripts/backup.sh >> /var/backups/reusehub/backup.log 2>&1
```

## Restore procedure

Test restores are part of the plan — a backup you have never restored is not a
backup.

```bash
# Untouched media first
docker run --rm -v reusehub_media:/media -v "$DEST:/backup" alpine \
  tar xzf /backup/<STAMP>.media.tar.gz -C /media

# Restore the database (this overwrites the current DB — use a scratch DB to test)
cat /var/backups/reusehub/<STAMP>.reusehub.sql.gz | gunzip |
  docker compose exec -T db psql -U "${POSTGRES_USER:-reusehub}" reusehub
```

The `pg_dump` plain-format output replays cleanly through `psql`. For a careful
dry run, restore into a scratch database first (recreate it, then replay) so the
live data is never at risk.

## Non-Docker / VPS summary

If you ran the bare-VPS path instead, the same plan applies with host tools:

```bash
pg_dump -U reusehub reusehub | gzip > "$DEST/$(date +%Y%m%d-%H%M%S).sql.gz"
tar czf "$DEST/$(date +%Y%m%d-%H%M%S).media.tar.gz" -C /path/to/backend media/
```

## How often / retention

- **Frequency**: nightly (cron at 02:00). A demo-day copy can be taken manually
  right before the presentation.
- **Retention**: 7 days of dumps on local disk. Enough to recover from an
  overnight mistake; dump files are small for this dataset.

## Failure scenarios covered

| Scenario | Recovery |
|----------|----------|
| DB container corrupted / volume deleted | Restore the latest `.sql.gz`; keep `media/` |
| Lost media files | Restore the matching `.media.tar.gz` |
| Accidental data change (e.g. a destructive admin action) | Restore the newest pre-incident dump |
| Entire host lost | Re-provision host, clone repo, restore latest dump + media from off-site copy |

## What is intentionally out of scope

- Point-in-time recovery (WAL archiving/PITR) — over-engineered for this size.
- Multi-region/high-availability replicas — not needed for a demo.
- Object-storage auto-backups — optional; the off-site copy is a manual step.