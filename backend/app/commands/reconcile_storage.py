"""Storage reconciliation CLI.

Usage:
    python -m app.commands.reconcile_storage --dry-run
    python -m app.commands.reconcile_storage --fix
    python -m app.commands.reconcile_storage --fix --delete-orphans
    python -m app.commands.reconcile_storage --dry-run --tenant <uuid>

Dry-run is the default. ``--delete-orphans`` is ignored unless ``--fix`` is
also supplied. The command never performs a cloud or cross-tenant deletion
outside the explicitly scoped tenant prefix.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

from app.database.session import async_session_factory
from app.services.storage_reconciliation import reconcile_storage
from app.storage import get_storage_provider


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile document rows with stored objects (dry-run by default)."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only; do not modify rows or objects (default).",
    )
    mode.add_argument(
        "--fix",
        action="store_true",
        help="Mark documents with missing objects as FAILED (does not delete DB rows).",
    )
    parser.add_argument(
        "--delete-orphans",
        action="store_true",
        help="With --fix, delete objects that have no DB reference in the scanned tenant.",
    )
    parser.add_argument(
        "--tenant",
        type=uuid.UUID,
        default=None,
        help="Restrict reconciliation to one tenant UUID.",
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    storage = get_storage_provider()
    async with async_session_factory() as session:
        report = await reconcile_storage(
            session,
            storage,
            tenant_id=args.tenant,
            fix=bool(args.fix),
            delete_orphans=bool(args.delete_orphans),
        )

    print(json.dumps(report, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.delete_orphans and not args.fix:
        print(
            "NOTE: --delete-orphans has no effect without --fix; running dry-run.",
            file=sys.stderr,
        )
    try:
        exit_code = asyncio.run(_run(args))
    except Exception as exc:
        print(f"Reconciliation failed: {type(exc).__name__}", file=sys.stderr)
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
