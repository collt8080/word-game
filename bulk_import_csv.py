import argparse
import csv
from pathlib import Path

from word_store import TursoWordStore


REQUIRED_COLUMNS = {
    "word",
    "first_letter",
    "last_letter",
    "word_type",
}


def read_records(source):
    with source.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV columns missing: {', '.join(sorted(missing))}")
        for row in reader:
            yield {"word": row["word"], "word_type": row["word_type"]}


def main():
    parser = argparse.ArgumentParser(
        description="Replace words data with a filtered CSV using bulk batches."
    )
    parser.add_argument("source", type=Path, nargs="?", default=Path("words_import.csv"))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete all current words before importing the CSV.",
    )
    args = parser.parse_args()
    if not args.source.exists():
        parser.error(f"CSV file not found: {args.source}")
    if args.batch_size < 1 or args.retries < 0 or args.retry_delay < 0:
        parser.error("batch-size must be positive; retries and retry-delay cannot be negative")
    if not args.replace:
        parser.error("Add --replace to confirm deleting current words")

    records = list(read_records(args.source))
    store = TursoWordStore()
    try:
        store.initialize()
        store.connection.execute("DELETE FROM words")
        store.connection.commit()
        print(f"기존 words 데이터 삭제 완료. {len(records)}개 import 시작", flush=True)

        total_batches = (len(records) + args.batch_size - 1) // args.batch_size

        def report_progress(batch_number, batch_count):
            print(f"배치 {batch_number}/{batch_count} 완료", flush=True)

        imported = store.add_word_records(
            records,
            registered_by="csv_import",
            dictionary_registered=True,
            notes=f"source: {args.source.name}",
            batch_size=args.batch_size,
            progress=report_progress,
            retries=args.retries,
            retry_delay=args.retry_delay,
            skip_existing=False,
        )
        print(f"완료: {imported}개 단어 import", flush=True)
    finally:
        store.close()


if __name__ == "__main__":
    main()
