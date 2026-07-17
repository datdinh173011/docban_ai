import argparse
import asyncio
import logging
from pathlib import Path

from rich.console import Console

from app.config import get_settings
from app.db import create_database_engine
from app.legal_package import PackageError, import_package, read_json, record_package_evaluation, register_sources, validate_package_manifest, validate_registry_document, publish_package
from app.knowledge_ingestion import ManifestError, import_manifest, publish_document, read_manifest, validate_manifest

logger = logging.getLogger(__name__)
console = Console()


async def run(arguments: argparse.Namespace) -> int:
    if arguments.command in {"registry-validate", "registry-register"}:
        try:
            document = read_json(arguments.registry)
        except PackageError as exc:
            console.print(f"[red]Registry không hợp lệ:[/red] {exc}")
            return 1
        errors = validate_registry_document(document)
        if errors:
            console.print(f"[red]Registry không hợp lệ:[/red] {', '.join(errors)}")
            return 1
        if arguments.command == "registry-validate":
            console.print("[green]Registry hợp lệ.[/green]")
            return 0
        settings = get_settings()
        engine = create_database_engine(settings)
        try:
            count = await register_sources(engine, document)
            console.print(f"[green]Đã đăng ký[/green] {count} nguồn registry.")
        finally:
            await engine.dispose()
        return 0
    if arguments.command in {"package-validate", "package-import", "package-publish", "package-record-evaluation"}:
        if arguments.command in {"package-publish", "package-record-evaluation"}:
            manifest = None
            errors: list[str] = []
        else:
            try:
                manifest = read_json(arguments.manifest)
            except PackageError as exc:
                console.print(f"[red]Package không hợp lệ:[/red] {exc}")
                return 1
            errors = validate_package_manifest(manifest)
        if errors:
            console.print(f"[red]Package không hợp lệ:[/red] {', '.join(errors)}")
            return 1
        if arguments.command == "package-validate":
            console.print("[green]Package hợp lệ.[/green]")
            return 0
        settings = get_settings()
        engine = create_database_engine(settings)
        try:
            if arguments.command == "package-import":
                result = await import_package(engine, settings, manifest)
                console.print(f"[green]Đã import package[/green] {result['package_code']} ({result['documents']} documents, {result['chunks']} chunks)")
            elif arguments.command == "package-record-evaluation":
                report = read_json(arguments.report)
                await record_package_evaluation(engine, arguments.package_code, arguments.version, report)
                console.print(f"[green]Đã ghi nhận evaluation pass[/green] {arguments.package_code} v{arguments.version}")
            else:
                await publish_package(engine, arguments.package_code, arguments.version)
                console.print(f"[green]Đã publish package[/green] {arguments.package_code} v{arguments.version}")
        except PackageError as exc:
            logger.warning("knowledge_package_cli_failed code=%s", exc)
            console.print(f"[red]Không thể hoàn tất:[/red] {exc}")
            return 1
        finally:
            await engine.dispose()
        return 0
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
    registry_validate = commands.add_parser("registry-validate")
    registry_validate.add_argument("registry", type=Path)
    registry_register = commands.add_parser("registry-register")
    registry_register.add_argument("registry", type=Path)
    package_validate = commands.add_parser("package-validate")
    package_validate.add_argument("manifest", type=Path)
    package_import = commands.add_parser("package-import")
    package_import.add_argument("manifest", type=Path)
    package_publish = commands.add_parser("package-publish")
    package_publish.add_argument("package_code")
    package_publish.add_argument("version", type=int)
    package_record_evaluation = commands.add_parser("package-record-evaluation")
    package_record_evaluation.add_argument("package_code")
    package_record_evaluation.add_argument("version", type=int)
    package_record_evaluation.add_argument("report", type=Path)
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
