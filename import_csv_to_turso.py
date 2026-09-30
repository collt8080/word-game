import argparse
import csv
from pathlib import Path

from word_store import TursoWordStore


CSV_FIELDS = {
    "word",
    "first_letter",
    "last_letter",
    "word_type",
    "dictionary_registered",
    "registered_by",
    "registered_at",
    "notes",
}


def read_csv_records(source):
    with source.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        fields = set(reader.fieldnames or [])
        missing = CSV_FIELDS - fields
        if missing:
            raise ValueError(f"CSV columns missing: {', '.join(sorted(missing))}")
        for row in reader:
            yield {"word": row["word"], "word_type": row["word_type"]}


def main():
    parser = argparse.ArgumentParser(
        description="Import a generated CSV into the existing Turso words table."
    )
    parser.add_argument("source", nargs="?", type=Path, default=Path("words_import.csv"))
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if not args.source.exists():
        parser.error(f"CSV file not found: {args.source}")
    store = TursoWordStore()
    try:
        store.initialize()
        records = list(read_csv_records(args.source))
        total_batches = (len(records) + args.batch_size - 1) // args.batch_size

        def report_progress(batch_number, batch_count):
            print(
                f"배치 {batch_number}/{batch_count} 완료",
                flush=True,
            )

        imported = store.add_word_records(
            records,
            registered_by="csv_import",
            dictionary_registered=True,
            notes=f"source: {args.source.name}",
            batch_size=args.batch_size,
            progress=report_progress,
            skip_existing=True,
        )
        print(f"완료: 새로 등록한 단어 {imported}개")
    finally:
        store.close()


if __name__ == "__main__":
    main()
