"""Export documents from a MongoDB collection as MongoDB Extended JSON."""

import argparse
import os
import sys
from pathlib import Path
from typing import TextIO

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


def non_negative_int(value: str) -> int:
    """Parse a non-negative integer for the document limit."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def export_documents(
    output: TextIO, uri: str, database: str, collection: str, limit: int
) -> int:
    """Write matching collection documents as a JSON array and return its size."""
    count = 0
    with MongoClient(uri, serverSelectionTimeoutMS=10_000) as client:
        client.admin.command("ping")
        documents = client[database][collection].find({})
        if limit:
            documents = documents.limit(limit)

        output.write("[\n")
        for document in documents:
            if count:
                output.write(",\n")
            output.write(json_util.dumps(document, indent=2))
            count += 1
        output.write("\n]\n")
    return count


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(
        description="Export documents from a MongoDB collection to Extended JSON."
    )
    parser.add_argument("--database", required=True, help="MongoDB database name")
    parser.add_argument("--collection", required=True, help="MongoDB collection name")
    parser.add_argument(
        "--limit",
        type=non_negative_int,
        default=1000,
        help="maximum number of documents (default: 1000; use 0 for no limit)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="output file; if omitted, write JSON to standard output",
    )
    args = parser.parse_args()

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        parser.error("set the MONGODB_URI environment variable before running")

    try:
        if args.output:
            with args.output.open("w", encoding="utf-8") as output:
                count = export_documents(
                    output, uri, args.database, args.collection, args.limit
                )
        else:
            count = export_documents(
                sys.stdout, uri, args.database, args.collection, args.limit
            )
    except PyMongoError as exc:
        print(f"MongoDB error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Could not write output: {exc}", file=sys.stderr)
        return 1

    print(f"Exported {count} document(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
