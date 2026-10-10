# Permanent conversation backups

Historical tar.gz setup report. The periodic tar.gz timer described below is now inactive in the current operating configuration; Borg handles periodic backups. See the README for current operation.

Primary: `~/Enikk-backups/backups`.
Secondary example: `/mnt/디스크이름/Enikk-backups/backups`. Replace the mount path with your actual backup disk; no fixed device name is required.
Settings: `~/.config/codex_enikk/backup.json`.

New backups retain the original archive manifest, SQLite snapshots and rollout validation. Secondary copies use temporary files, fsync, SHA256 verification, and publication without replacing existing backups. Missing disk mounts raise an error and preserve the primary archive. Home backup paths under a Git repository require an ignore rule.

The installed wrapper was backed up before replacement under `~/.local/state/codex_enikk/backups/permanent-backup-20261010T022937Z`. The existing Enikk process and conversation were not restarted or modified.

User systemd timer `enikk-conversation-backup.timer` adds backups every 15 minutes, independently of the running wrapper. Startup and graceful exit backups continue. No automatic deletion or retention pruning is configured.

Validation: 46 existing wrapper tests and 2 new secondary-copy tests passed. Historical migration is recorded in `~/Enikk-backup-migration.log`; all old archives remain in `/var/tmp/codex_enikk-사용자UID/backups`. Completion and SHA256 inventory are recorded in `~/Enikk-backups/migration-verification.json` when migration finishes. Fresh backup log: `~/Enikk-backups/fresh-backup.log`.
