# Disaster Recovery Runbook · Ome365 v1.0

> **RPO** (Recovery Point Objective): **1 hour** — at most 1 hour of data lost
> **RTO** (Recovery Time Objective): **4 hours** — service back online within 4 hours
>
> Last updated: 2026-05-08 · v1.0-rc1

This runbook covers backup, recovery, and cross-region failover for self-hosted Ome365 deployments.

---

## 0 · Pre-incident: Backup setup

### 0.1 What to back up

```
$OME365_VAULT/                    # markdown vault (source of truth)
├── Knowledge/entities/           # Hike L1 entity files
├── Notes/ Journal/ Decisions/    # daily content
├── Projects/ Contacts/ Memory/   # work + personal
└── TicNote/                      # interview transcripts (if used)

$OME365_HOME/ (default ~/.ome365) # platform metadata
├── tenants/<id>/db.sqlite         # multi-tenant sessions
└── magic_tokens.db / sessions.db

.app/cockpit_config.json          # PII config (gitignored)
.app/tenant_config.json           # tenant brand
.app/share_registry.json          # share station registry
.app/share_auth.db                # password hashes + audit log (SQLite)
.app/master.key                   # Fernet master key (44 bytes · CRITICAL)
.app/settings.json                # API keys
skills/truthguard/truth.yml       # canonical names dict
```

### 0.2 Backup strategy (3-2-1 rule)

- **3** copies of data: live + 2 backups
- **2** different storage media: local SSD + remote object store
- **1** copy off-site: cross-region (e.g. Beijing primary + Shanghai DR)

#### Daily local backup (cron · runs at 02:00)

```bash
#!/usr/bin/env bash
# /usr/local/bin/ome365-backup-daily
# Cron: 0 2 * * * /usr/local/bin/ome365-backup-daily
set -euo pipefail

VAULT="${OME365_VAULT:-/var/lib/ome365/vault}"
HOME_DIR="${OME365_HOME:-/var/lib/ome365}"
BACKUP_DIR="/var/backups/ome365"
DATE=$(date +%Y%m%d_%H%M)

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

# 1. Vault rsync (incremental · fast)
rsync -aH --delete \
  "$VAULT/" "$BACKUP_DIR/daily/vault-$DATE/"

# 2. SQLite hot backup (use sqlite3 .backup · not file copy)
for db in "$HOME_DIR"/tenants/*/db.sqlite "$HOME_DIR/sessions.db" "$HOME_DIR/magic_tokens.db" \
          ".app/share_auth.db"; do
  [ -f "$db" ] || continue
  name=$(basename "$db" .sqlite)
  parent=$(basename "$(dirname "$db")")
  sqlite3 "$db" ".backup '$BACKUP_DIR/daily/${parent}-${name}-$DATE.sqlite'"
done

# 3. Critical config snapshots (tar · small)
tar czf "$BACKUP_DIR/daily/config-$DATE.tar.gz" \
  .app/cockpit_config.json \
  .app/tenant_config.json \
  .app/share_registry.json \
  .app/master.key \
  skills/truthguard/truth.yml \
  2>/dev/null || true

# 4. Rotate: keep 7 daily, 4 weekly, 12 monthly
find "$BACKUP_DIR/daily" -mtime +7 -delete
[ "$(date +%u)" = "7" ] && cp -al "$BACKUP_DIR/daily/vault-$DATE" "$BACKUP_DIR/weekly/" 2>/dev/null
find "$BACKUP_DIR/weekly" -mtime +28 -delete

echo "✓ Backup complete: $DATE"
```

#### Hourly off-site sync (cron · runs every hour)

```bash
# /usr/local/bin/ome365-backup-hourly
# Cron: 0 * * * * /usr/local/bin/ome365-backup-hourly
set -euo pipefail

# Push critical files to S3 (or compatible · MinIO/阿里 OSS/腾讯 COS)
aws s3 sync /var/backups/ome365/daily/ s3://ome365-dr/$(hostname)/ \
  --exclude '*' --include '*.sqlite' --include 'config-*.tar.gz' \
  --storage-class STANDARD_IA

# Vault delta (rsync to remote DR site)
rsync -aH --delete --rsh="ssh -p 22" \
  /var/lib/ome365/vault/ \
  ome365-dr-replica:/var/lib/ome365/vault/
```

### 0.3 Backup verification (weekly · automated)

```bash
# Restore latest backup to /tmp/dr-test/ · boot test server · curl /api/dashboard
mkdir -p /tmp/dr-test
LATEST=$(ls -t /var/backups/ome365/daily/vault-* | head -1)
rsync -aH "$LATEST/" /tmp/dr-test/vault/

OME365_VAULT=/tmp/dr-test/vault OME365_PORT=3699 \
  python3 /opt/ome365/.app/server.py > /tmp/dr-test.log 2>&1 &
sleep 5

CODE=$(curl -s --noproxy localhost -o /dev/null -w "%{http_code}" http://localhost:3699/api/dashboard)
[ "$CODE" = "200" ] && echo "✓ DR weekly drill OK" || \
  ( echo "✗ DR DRILL FAILED — INVESTIGATE"; mail -s "Ome365 DR drill failed" ops@example.com < /tmp/dr-test.log )

pkill -f "OME365_PORT=3699"
rm -rf /tmp/dr-test
```

---

## 1 · Incident: Database corruption

**Symptom**: SQLite file corrupted · `database disk image is malformed` · share_auth.db / sessions.db unreadable.

**Detection**: `/api/share/list` → 500 · server.py log shows `sqlite3.DatabaseError`.

**Recovery (RTO < 30 min)**:

```bash
# 1. Stop server (no new writes)
systemctl stop ome365 ome365-share

# 2. Quarantine corrupt file (forensics)
mv .app/share_auth.db /var/quarantine/share_auth.db.$(date +%s)

# 3. Restore latest known-good backup
LATEST=$(ls -t /var/backups/ome365/daily/share_auth-*.sqlite | head -1)
cp "$LATEST" .app/share_auth.db
chown ome365:ome365 .app/share_auth.db
chmod 600 .app/share_auth.db

# 4. Verify integrity
sqlite3 .app/share_auth.db "PRAGMA integrity_check"  # → "ok"

# 5. Restart
systemctl start ome365 ome365-share

# 6. Smoke test
curl -fsS http://localhost:3650/api/share/list | jq '.items | length'
```

**Data loss tolerance**: ≤ 1 hour (since last hourly backup).

---

## 2 · Incident: Vault disk failure

**Symptom**: `OSError: I/O error` on vault read · disk SMART warnings.

**Detection**: server.py boot fails · log shows file read errors on `Knowledge/`, `Journal/`, etc.

**Recovery (RTO < 4h · depends on disk size)**:

```bash
# 1. Stop service
systemctl stop ome365 ome365-share

# 2. Mount replacement disk (or use DR replica)
mount /dev/sdb1 /var/lib/ome365-new

# 3. Restore from latest weekly + apply daily delta
LATEST_WEEKLY=$(ls -td /var/backups/ome365/weekly/vault-* | head -1)
LATEST_DAILY=$(ls -td /var/backups/ome365/daily/vault-* | head -1)
rsync -aH "$LATEST_WEEKLY/" /var/lib/ome365-new/vault/
rsync -aH "$LATEST_DAILY/" /var/lib/ome365-new/vault/  # apply delta

# 4. Re-link
mv /var/lib/ome365 /var/lib/ome365-broken
mv /var/lib/ome365-new /var/lib/ome365
chown -R ome365:ome365 /var/lib/ome365

# 5. Restart + verify
systemctl start ome365 ome365-share
curl -fsS http://localhost:3650/api/dashboard
```

---

## 3 · Incident: Cross-region failover

**Scenario**: Primary region (e.g. Beijing) datacenter outage · need to failover to DR site (Shanghai).

**Pre-requisite**: hourly rsync to DR replica is running (see §0.2).

**Failover (RTO < 1h)**:

```bash
# On DR site (Shanghai replica):

# 1. Verify replica freshness
ls -la /var/lib/ome365/vault/.last-rsync  # < 1h old

# 2. Promote to primary
systemctl start ome365 ome365-share

# 3. DNS / load balancer cutover
# Update DNS A record: ome365.your-corp.com → DR site IP
# (or update HAProxy / nginx upstream)

# 4. Notify users
echo "Ome365 failed over to DR site at $(date)" | \
  mail -s "Ome365 DR failover" all-users@your-corp.com
```

**Failback** (when primary recovers):

```bash
# 1. Sync delta from DR back to primary
rsync -aH --delete \
  ome365-dr-replica:/var/lib/ome365/vault/ \
  /var/lib/ome365/vault/

# 2. Stop DR · start primary
ssh ome365-dr-replica systemctl stop ome365 ome365-share
systemctl start ome365 ome365-share

# 3. DNS cutover back
```

---

## 4 · Incident: master.key loss / corruption

**Critical**: Loss of `.app/master.key` means **all Fernet-encrypted share passwords are unrecoverable**.

**Mitigation**:
- master.key MUST be in 3-2-1 backup (encrypted with offline GPG key)
- Quarterly key rotation (generates new key · re-encrypts all `password_enc` fields)

**Recovery if lost**:
1. Restore master.key from offline backup (USB drive / HSM / GPG-encrypted email)
2. If truly lost: rotate all share passwords (admin manually re-shares)
3. Notify all share-link recipients

```bash
# Recovery
cp /secure-backup/master.key .app/master.key
chmod 600 .app/master.key
systemctl restart ome365-share

# If lost forever — bulk reset all share passwords:
sqlite3 .app/share_auth.db "UPDATE shares SET password_enc = NULL WHERE password_enc IS NOT NULL"
# admin then must re-set passwords for all shares (out-of-band)
```

---

## 5 · Incident: Tenant data corruption (multi-tenant)

**Symptom**: One tenant's vault corrupted · others unaffected.

**Recovery (RTO < 30 min)**:

```bash
TENANT_ID="acme-corp"  # affected tenant

# 1. Disable tenant (return 503 from middleware)
sqlite3 ~/.ome365/tenants/$TENANT_ID/db.sqlite \
  "UPDATE tenants SET status='maintenance' WHERE id='$TENANT_ID'"

# 2. Restore tenant-specific paths
LATEST=$(ls -td /var/backups/ome365/daily/vault-* | head -1)
rsync -aH "$LATEST/Projects/Tenants/$TENANT_ID/" \
  /var/lib/ome365/vault/Projects/Tenants/$TENANT_ID/

# 3. Re-enable
sqlite3 ~/.ome365/tenants/$TENANT_ID/db.sqlite \
  "UPDATE tenants SET status='active' WHERE id='$TENANT_ID'"

# 4. Notify tenant admin
```

---

## 6 · Drill schedule

| Frequency | Drill | Acceptance |
|:---|:---|:---|
| **Weekly** | Backup restore to /tmp/dr-test (automated) | curl /api/dashboard = 200 |
| **Monthly** | Full vault restore from weekly backup | < 4h end-to-end |
| **Quarterly** | Cross-region failover drill (50% traffic) | < 1h cutover |
| **Yearly** | Complete DR scenario · run from DR site only for 24h | Zero customer impact |

---

## 7 · Contact escalation

| Tier | Role | SLA |
|:---|:---|:---|
| L1 | Self-host operator | Auto-respond < 5 min |
| L2 | Ome365 maintainer | < 24h response (community Discord / GitHub) |
| L3 | Enterprise support | < 4h (paid tier · contact: see SECURITY.md) |

---

## 8 · Post-incident actions

After every incident:

1. Create GitHub Issue with `incident` label (postmortem · what failed · what was learned)
2. Update this runbook if a gap is found
3. Add a new test case to `tests/` if applicable
4. Schedule a drill within 30 days to verify the fix

> *RPO/RTO are aspirational targets · validate every quarter via drill (§6).*
