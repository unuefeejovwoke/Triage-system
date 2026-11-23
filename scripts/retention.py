"""Delete consultation records older than the retention period (RETENTION_DAYS in .env).

    python -m scripts.retention            # dry run: only shows what would be deleted
    python -m scripts.retention --delete   # actually delete

Schedule it to run regularly, for example monthly with Windows Task Scheduler.
"""
import argparse

from app.database import SessionLocal
from app.retention import purge_old_consultations


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply the data retention policy.")
    parser.add_argument("--delete", action="store_true", help="Actually delete. Without this, nothing is changed.")
    parser.add_argument("--days", type=int, help="Override RETENTION_DAYS for this run.")
    args = parser.parse_args()
    with SessionLocal() as db:
        r = purge_old_consultations(db, dry_run=not args.delete, days=args.days)
    print(f"Retention period: {r['retention_days']} days (records before {r['cutoff']})")
    if r["dry_run"]:
        print(f"Would delete: {r['matched']} consultation(s). Run again with --delete to remove them.")
    else:
        print(f"Deleted: {r['deleted']} consultation(s). This was recorded in the audit log.")


if __name__ == "__main__":
    main()
