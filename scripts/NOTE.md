# Legacy Scripts

The scripts in this directory are retained for backward compatibility and migration support.

Current active deployment is Docker Compose (`docker-compose.yml`) with containerized services.
Systemd-based install/scheduling scripts are legacy and are not actively used for the main runtime.

Use these scripts only if you are migrating an older host-based setup or need host-side helper tasks
(for example, removable media mount/unmount helpers).
