import argparse
import asyncio
import logging
from pathlib import Path

from rich.console import Console

from app.config import get_settings
from app.db import create_database_engine
from app.knowledge_ingestion import ManifestError, import_manifest, publish_document, read_manifest, validate_manifest

logger = logging.getLogger(__name__)
console = Console()


async def run(arguments: argparse.Namespace) -> int:
    if arguments.command == "validate":
        manifest = read_manifest(arguments.manifest)
        errors = validate_manifest(manifest)
        if errors:
            console.print(f"[red]Manifest không hợp lệ:[/red] {', '.join(errors)}")
            return 1
        console.print("[green]Manifest hợp lệ.[/green]")
        return 0
    settings = get_settings()
    engine = create_database_engine(settings)
    try:
        if arguments.command == "import":
            result = await import_manifest(engine, settings, arguments.manifest)
            console.print(f"[green]Đã import[/green] {result['document_code']} ({result['chunks']} chunks)")
        else:
            await publish_document(engine, settings, arguments.document_code)
            console.print(f"[green]Đã publish[/green] {arguments.document_code}")
    except ManifestError as exc:
        logger.warning("knowledge_cli_failed code=%s", exc)
        console.print(f"[red]Không thể hoàn tất:[/red] {exc}")
        return 1
    finally:
        await engine.dispose()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="ICIVI knowledge-base operator CLI")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("manifest", type=Path)
    import_command = commands.add_parser("import")
    import_command.add_argument("manifest", type=Path)
    publish = commands.add_parser("publish")
    publish.add_argument("document_code")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
