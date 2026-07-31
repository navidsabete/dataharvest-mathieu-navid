import argparse
from dataharvest.config import Config
from dataharvest.store import Store
from dataharvest.fetcher import Fetcher
from dataharvest.pipeline import GenericPipeline
from dataharvest.validator import Validator

#TODO():from dataharvest.orchestrator import Orchestrator


def build_parser():
    parser = argparse.ArgumentParser(prog="dataharvest", description="DataHarvest App CLI")

    subparsers = parser.add_subparsers(dest="command")
    crawl = subparsers.add_parser("crawl", help="Lance un scraping")
    crawl.add_argument("--config", required=True)
    crawl.add_argument("--dry-run", action="store_true")

    export = subparsers.add_parser("export", help="Exporte un store")
    export.add_argument("--from", dest="source", required=True)
    export.add_argument( "--to", dest="target", required=True)

    validate = subparsers.add_parser("validate", help="Valide une configuration")
    validate.add_argument("--config", required=True)

    return parser


def command_validate(args):
    Config(args.config)
    print("Configuration valide")


def command_export(args):
    source = detect_backend(args.source)
    target = detect_backend(args.target)
    store = Store(source, args.source)
    count = store.export_to(target, args.target)
    print(f"{count} items exportés")


def command_crawl(args):
    config = Config(args.config)
    #TODO:()
    #orchestrator = Orchestrator(config)
    #orchestrator.run(dry_run=args.dry_run)

def detect_backend(path):
    extension = path.split(".")[-1]

    if extension == "json":
        return "json"
    if extension == "csv":
        return "csv"
    if extension in ("db", "sqlite"):
        return "sqlite"
    raise ValueError("Backend impossible à détecter")


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "crawl":
        command_crawl(args)
    elif args.command == "export":
        command_export(args)
    elif args.command == "validate":
        command_validate(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()