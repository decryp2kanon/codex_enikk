# Permanent conversation backups

Primary: `~/Enikk-backups/backups`.
Secondary: `/mnt/hdd4t_2nd/Enikk-backups/backups` on `/dev/sdd1`.
Settings: `~/.config/codex_enikk/backup.json`.

New backups retain the original archive manifest, SQLite snapshots and rollout validation. Secondary copies use temporary files, fsync, SHA256 verification, and publication without replacing existing backups. Missing disk mounts raise an error and preserve the primary archive. Home backup paths under a Git repository require an ignore rule.

The installed wrapper was backed up before replacement under `~/.local/state/codex_enikk/backups/permanent-backup-20261010T022937Z`. The existing Enikk process and conversation were not restarted or modified.

User systemd timer `enikk-conversation-backup.timer` adds backups every 15 minutes, independently of the running wrapper. Startup and graceful exit backups continue. No automatic deletion or retention pruning is configured.

Validation: 46 existing wrapper tests and 2 new secondary-copy tests passed. Historical migration is recorded in `~/Enikk-backup-migration.log`; all old archives remain in `/var/tmp/codex_enikk-1000/backups`. Completion and SHA256 inventory are recorded in `~/Enikk-backups/migration-verification.json` when migration finishes. Fresh backup log: `~/Enikk-backups/fresh-backup.log`.
