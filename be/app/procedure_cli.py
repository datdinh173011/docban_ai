"""Operator commands for validating and exporting a DVC procedure snapshot."""

import argparse
import asyncio
from pathlib import Path

from rich.console import Console

from app.procedure_catalog import ProcedureCatalog
from app.config import get_settings
from app.db import create_database_engine
from app.procedure_ingestion import ProcedureImportError, import_snapshot, publish_snapshot
from app.procedure_pipeline import ReviewRegistry

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="ICIVI DVC snapshot importer")
    parser.add_argument("snapshot_dir", type=Path, nargs="?")
    parser.add_argument("--export", type=Path, help="Write the normalized immutable catalog JSON")
    parser.add_argument("--review-registry", type=Path, help="Validate operator-reviewed PDF sections")
    parser.add_argument("--import-snapshot", metavar="CODE", help="Import configured snapshot to PostgreSQL")
    parser.add_argument("--publish-snapshot", metavar="CODE", help="Publish an imported snapshot")
    arguments = parser.parse_args()
    if arguments.import_snapshot or arguments.publish_snapshot:
        async def run() -> None:
            engine = create_database_engine(get_settings())
            try:
                if arguments.import_snapshot:
                    result = await import_snapshot(engine, get_settings(), arguments.import_snapshot)
                    console.print(f"[green]Đã import snapshot[/green] {result}")
                else:
                    await publish_snapshot(engine, arguments.publish_snapshot)
                    console.print(f"[green]Đã publish snapshot[/green] {arguments.publish_snapshot}")
            finally:
                await engine.dispose()
        try:
            asyncio.run(run())
        except ProcedureImportError as exc:
            console.print(f"[red]Không thể import snapshot:[/red] {exc}")
            raise SystemExit(1) from exc
        return
    if arguments.snapshot_dir is None:
        parser.error("snapshot_dir is required unless importing or publishing")
    try:
        catalog = ProcedureCatalog.from_snapshot(arguments.snapshot_dir)
        reviews = ReviewRegistry.load(arguments.review_registry)
    except (OSError, ValueError, KeyError) as exc:
        console.print(f"[red]Snapshot không hợp lệ:[/red] {exc}")
        raise SystemExit(1) from exc
    if arguments.export:
        catalog.dump(arguments.export)
        console.print(f"[green]Đã export catalog[/green] {arguments.export} ({len(catalog.records)} thủ tục).")
        return
    sections = sum(len(record.sections) for record in catalog.records)
    warnings = sum(record.data_warning != "Không có cảnh báo tự động" for record in catalog.records)
    reviewed = sum(len(values) for values in reviews.approved.values())
    console.print(f"[green]Snapshot hợp lệ.[/green] {len(catalog.records)} thủ tục, {sections} sections, {warnings} bản ghi cần review, {reviewed} section approvals.")


if __name__ == "__main__":
    main()
