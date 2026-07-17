import argparse
import asyncio
import json
import logging
from pathlib import Path

from rich.console import Console

from app.config import get_settings
from app.db import create_database_engine
from app.form_ingestion import (
    build_form_draft,
    import_form_corpus,
    inspect_form_corpus,
    publish_form,
    source_specs,
)

logger = logging.getLogger(__name__)
console = Console()


async def run(arguments: argparse.Namespace) -> int:
    if arguments.import_db and arguments.source_dir is None:
        console.print("[red]--source-dir là bắt buộc khi import PDF.[/red]")
        return 1
    if arguments.import_db or arguments.publish:
        settings = get_settings()
        engine = create_database_engine(settings)
        try:
            if arguments.import_db:
                results = await import_form_corpus(engine, settings, arguments.source_dir)
                console.print(f"[green]Đã tạo hoặc kiểm tra[/green] {len(results)} trusted source records.")
            if arguments.publish:
                await publish_form(engine, settings, arguments.publish)
                console.print(f"[green]Đã publish form[/green] {arguments.publish}")
        except ValueError as exc:
            logger.warning("form_cli_failed code=%s", exc)
            console.print(f"[red]Không thể hoàn tất:[/red] {exc}")
            return 1
        finally:
            await engine.dispose()
        return 0
    if arguments.source_dir is None:
        console.print("[red]--source-dir là bắt buộc khi kiểm tra PDF.[/red]")
        return 1
    inspections = inspect_form_corpus(arguments.source_dir)
    invalid = [inspection for inspection in inspections if not inspection.valid]
    for inspection in inspections:
        console.print(json.dumps(inspection.registry_payload(), ensure_ascii=False))
    if arguments.form_code:
        spec = next(spec for spec in source_specs().values() if spec.form_code == arguments.form_code)
        inspection = next(item for item in inspections if item.source_key == spec.source_key)
        console.print(json.dumps(build_form_draft(spec, inspection), ensure_ascii=False))
    return 1 if invalid else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="ICIVI trusted form PDF inspector")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--form-code")
    parser.add_argument("--import-db", action="store_true", help="Create immutable in-review form snapshots and records")
    parser.add_argument("--publish", metavar="FORM_CODE", help="Publish the latest technically valid in-review form")
    arguments = parser.parse_args()
    if arguments.import_db and arguments.publish:
        parser.error("--import-db and --publish are separate operator actions")
    raise SystemExit(asyncio.run(run(arguments)))


if __name__ == "__main__":
    main()
