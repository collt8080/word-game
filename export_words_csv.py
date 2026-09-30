import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

from preprocess import read_json_records


DEFAULT_SOURCE = Path(__file__).parent / "raw_data"
CSV_FIELDS = [
    "word",
    "first_letter",
    "last_letter",
    "word_type",
    "dictionary_registered",
    "registered_by",
    "registered_at",
    "notes",
]


def iter_unique_records(source):
    seen = set()
    sources = sorted(source.glob("*.json")) if source.is_dir() else [source]
    for json_file in sources:
        for record in read_json_records(json_file):
            word = record["word"]
            if word in seen:
                continue
            seen.add(word)
            yield {
                "word": word,
                "first_letter": word[0],
                "last_letter": word[-1],
                "word_type": record["word_type"],
                "dictionary_registered": 1,
                "registered_by": "json_import",
                "registered_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "notes": f"source: {json_file.name}",
            }


def main():
    parser = argparse.ArgumentParser(
        description="Export filtered Korean dictionary JSON data as a Turso CSV."
    )
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("words_import.csv"),
    )
    args = parser.parse_args()

    count = 0
    with args.output.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in iter_unique_records(args.source):
            writer.writerow(record)
            count += 1

    print(f"CSV 생성 완료: {args.output} ({count}개 단어)")


if __name__ == "__main__":
    main()
