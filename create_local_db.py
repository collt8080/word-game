import argparse
import csv
import sqlite3
from pathlib import Path


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


def create_database(csv_path, database_path, replace=False):
    if database_path.exists() and not replace:
        raise FileExistsError(
            f"{database_path} already exists. Use --replace to recreate it."
        )

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("DROP TABLE IF EXISTS words")
        connection.execute(
            """
            CREATE TABLE words (
                word TEXT PRIMARY KEY,
                first_letter TEXT NOT NULL,
                last_letter TEXT NOT NULL,
                word_type TEXT NOT NULL DEFAULT '',
                dictionary_registered INTEGER NOT NULL DEFAULT 0,
                registered_by TEXT,
                registered_at TEXT NOT NULL DEFAULT '',
                notes TEXT
            )
            """
        )
        connection.execute(
            "CREATE INDEX words_first_letter_idx ON words(first_letter)"
        )

        with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames != CSV_FIELDS:
                raise ValueError(
                    f"Unexpected CSV columns. Expected {CSV_FIELDS}, got {reader.fieldnames}"
                )

            rows = (
                (
                    row["word"],
                    row["first_letter"],
                    row["last_letter"],
                    row["word_type"],
                    int(row["dictionary_registered"]),
                    row["registered_by"],
                    row["registered_at"],
                    row["notes"],
                )
                for row in reader
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO words
                (word, first_letter, last_letter, word_type,
                 dictionary_registered, registered_by, registered_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        print(f"SQLite import complete: {count} words -> {database_path}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description="Create a local SQLite words database.")
    parser.add_argument("source", nargs="?", type=Path, default=Path("words_import.csv"))
    parser.add_argument("-o", "--output", type=Path, default=Path("words.sqlite3"))
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if not args.source.exists():
        parser.error(f"CSV file not found: {args.source}")
    create_database(args.source, args.output, replace=args.replace)


if __name__ == "__main__":
    main()
