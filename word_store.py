import os
import random
import re
from importlib import import_module
from pathlib import Path
from time import sleep

_DUEUM_TO_IEUNG_VOWELS = {2, 3, 6, 7, 12, 17, 20}

try:
    load_dotenv = getattr(import_module("dotenv"), "load_dotenv", None)
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(Path(__file__).with_name(".env"))


def normalize_word(word):
    if not word:
        return None
    word = re.sub(r"[^가-힣ㄱ-ㅎㅏ-ㅣ]", "", word.strip())
    jamo = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]")
    if len(word) < 2 or jamo.match(word[0]) or jamo.match(word[-1]):
        return None
    return word


def dueum_candidates(char):
    code = ord(char) - 0xAC00
    if not 0 <= code < 11172:
        return []

    leading = code // 588
    vowel = (code % 588) // 28
    trailing = code % 28
    candidates = []

    if leading == 5:
        candidates.append(11 if vowel in _DUEUM_TO_IEUNG_VOWELS else 2)
    elif leading == 2 and vowel in _DUEUM_TO_IEUNG_VOWELS:
        candidates.append(11)

    if not candidates:
        return []

    return [
        chr(0xAC00 + (replacement * 21 + vowel) * 28 + trailing)
        for replacement in candidates
    ]


class TursoWordStore:
    def __init__(self, connection=None):
        self._remote = connection is None
        self._turso_serverless = None
        self._database_url = None
        self._auth_token = None
        if connection is None:
            self._database_url = os.getenv("TURSO_DATABASE_URL")
            self._auth_token = os.getenv("TURSO_AUTH_TOKEN")
            if not self._database_url or not self._auth_token:
                raise RuntimeError(
                    "Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN before starting the game."
                )
            try:
                self._turso_serverless = import_module("turso_serverless")
            except ImportError as error:
                raise RuntimeError(
                    "Install the Turso driver with: pip install turso_serverless"
                ) from error
            connection = self._turso_serverless.connect(
                self._database_url,
                auth_token=self._auth_token,
            )

        self.connection = connection

    def _reconnect(self):
        if not self._remote:
            return
        try:
            self.connection.close()
        except Exception:
            pass
        self.connection = self._turso_serverless.connect(
            self._database_url,
            auth_token=self._auth_token,
        )

    @staticmethod
    def _is_retryable_error(error):
        message = str(error).lower()
        return isinstance(error, OSError) or any(
            marker in message
            for marker in (
                "ssl",
                "unexpected_eof",
                "timed out",
                "connection reset",
                "request to https",
                "stream not found",
            )
        )

    def _read_rows(self, statement, parameters=(), retries=5, retry_delay=2.0):
        for attempt in range(retries + 1):
            try:
                return self.connection.execute(statement, parameters).fetchall()
            except Exception as error:
                if (
                    not self._remote
                    or not self._is_retryable_error(error)
                    or attempt == retries
                ):
                    raise
                sleep(retry_delay * (2 ** attempt))
                self._reconnect()
        return []

    def initialize(self):
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS words (
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
        columns = {
            row[1]
            for row in self.connection.execute("PRAGMA table_info(words)").fetchall()
        }
        migrations = {
            "word_type": "ALTER TABLE words ADD COLUMN word_type TEXT NOT NULL DEFAULT ''",
            "dictionary_registered":
                "ALTER TABLE words ADD COLUMN dictionary_registered INTEGER NOT NULL DEFAULT 0",
            "registered_by": "ALTER TABLE words ADD COLUMN registered_by TEXT",
            "registered_at":
                "ALTER TABLE words ADD COLUMN registered_at TEXT NOT NULL DEFAULT ''",
            "notes": "ALTER TABLE words ADD COLUMN notes TEXT",
        }
        for column, statement in migrations.items():
            if column not in columns:
                self.connection.execute(statement)
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS words_first_letter_idx ON words(first_letter)"
        )
        self.connection.commit()

    def add_words(
        self,
        words,
        registered_by="preprocess",
        dictionary_registered=False,
        notes=None,
        batch_size=100,
        progress=None,
        retries=5,
        retry_delay=2.0,
        skip_existing=False,
    ):
        records = ({"word": word} for word in words)
        return self.add_word_records(
            records,
            registered_by=registered_by,
            dictionary_registered=dictionary_registered,
            notes=notes,
            batch_size=batch_size,
            progress=progress,
            retries=retries,
            retry_delay=retry_delay,
            skip_existing=skip_existing,
        )

    def add_word_records(
        self,
        records,
        registered_by="preprocess",
        dictionary_registered=False,
        notes=None,
        batch_size=100,
        progress=None,
        retries=5,
        retry_delay=2.0,
        skip_existing=False,
    ):
        rows = {}
        for record in records:
            word = record.get("word")
            normalized = normalize_word(word)
            if normalized:
                rows[normalized] = (
                    normalized,
                    normalized[0],
                    normalized[-1],
                    record.get("word_type", ""),
                    int(dictionary_registered),
                    registered_by,
                    notes,
                )

        if skip_existing and rows:
            existing_words = set(self.existing_words(rows))
            rows = {
                word: values
                for word, values in rows.items()
                if word not in existing_words
            }

        if rows:
            values = list(rows.values())
            statement = """
                INSERT INTO words
                (word, first_letter, last_letter, word_type, dictionary_registered,
                 registered_by, registered_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
                ON CONFLICT(word) DO UPDATE SET
                    first_letter = excluded.first_letter,
                    last_letter = excluded.last_letter,
                    word_type = excluded.word_type,
                    dictionary_registered = excluded.dictionary_registered,
                    registered_by = excluded.registered_by,
                    notes = excluded.notes
                """
            total_batches = (len(values) + batch_size - 1) // batch_size
            for batch_number, start in enumerate(
                range(0, len(values), batch_size), start=1
            ):
                batch_values = values[start:start + batch_size]
                for attempt in range(retries + 1):
                    try:
                        self.connection.executemany(statement, batch_values)
                        self.connection.commit()
                        break
                    except Exception as error:
                        if (
                            not self._remote
                            or not self._is_retryable_error(error)
                            or attempt == retries
                        ):
                            raise
                        try:
                            self.connection.rollback()
                        except Exception:
                            pass
                        sleep(retry_delay * (2 ** attempt))
                        self._reconnect()
                if progress:
                    progress(batch_number, total_batches)
        return len(rows)

    def existing_words(self, words):
        normalized_words = {
            normalized
            for word in words
            if (normalized := normalize_word(word))
        }
        if not normalized_words:
            return set()

        existing = set()
        values = list(normalized_words)
        for start in range(0, len(values), 100):
            batch = values[start:start + 100]
            placeholders = ", ".join("?" for _ in batch)
            rows = self._read_rows(
                f"SELECT word FROM words WHERE word IN ({placeholders})",
                batch,
            )
            existing.update(row[0] for row in rows)
        return existing

    def add_word(
        self, word, word_type="", dictionary_registered=False, registered_by=None, notes=None
    ):
        return self.add_word_records(
            [{"word": word, "word_type": word_type}],
            registered_by=registered_by,
            dictionary_registered=dictionary_registered,
            notes=notes,
        )

    def contains(self, word):
        normalized = normalize_word(word)
        if not normalized:
            return False
        rows = self._read_rows(
            "SELECT 1 FROM words WHERE word = ? LIMIT 1", (normalized,)
        )
        return bool(rows)

    def get_word(self, word):
        normalized = normalize_word(word)
        if not normalized:
            return None
        rows = self._read_rows(
            """
            SELECT word, word_type, dictionary_registered, registered_by, registered_at, notes
            FROM words WHERE word = ?
            """,
            (normalized,),
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "word": row[0],
            "word_type": row[1],
            "dictionary_registered": bool(row[2]),
            "registered_by": row[3],
            "registered_at": row[4],
            "notes": row[5],
        }

    def set_dictionary_status(self, word, registered, registered_by=None, notes=None):
        normalized = normalize_word(word)
        if not normalized:
            return False
        cursor = self.connection.execute(
            """
            UPDATE words
            SET dictionary_registered = ?, registered_by = COALESCE(?, registered_by),
                notes = COALESCE(?, notes)
            WHERE word = ?
            """,
            (int(registered), registered_by, notes, normalized),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def next_word(self, last_letter, used_words, use_dueum=True, difficulty="상"):
        starting_letters = [last_letter]
        if use_dueum:
            starting_letters.extend(dueum_candidates(last_letter))

        placeholders = ", ".join("?" for _ in starting_letters)
        candidate_rows = self._read_rows(
            f"""
            SELECT word, last_letter
            FROM words
            WHERE first_letter IN ({placeholders})
            ORDER BY word
            """,
            starting_letters,
        )
        used = set(used_words)
        candidates = [row for row in candidate_rows if row[0] not in used]
        if not candidates:
            return None

        continuation_letters = set()
        for _, candidate_last_letter in candidates:
            continuation_letters.add(candidate_last_letter)
            if use_dueum:
                continuation_letters.update(dueum_candidates(candidate_last_letter))

        count_placeholders = ", ".join("?" for _ in continuation_letters)
        count_parameters = list(continuation_letters)
        count_statement = (
            f"SELECT first_letter, COUNT(*) FROM words "
            f"WHERE first_letter IN ({count_placeholders})"
        )
        if used:
            used_placeholders = ", ".join("?" for _ in used)
            count_statement += f" AND word NOT IN ({used_placeholders})"
            count_parameters.extend(used)
        count_statement += " GROUP BY first_letter"
        counts = dict(self._read_rows(count_statement, count_parameters))

        def continuation_count(candidate):
            letters = [candidate[1]]
            if use_dueum:
                letters.extend(dueum_candidates(candidate[1]))
            return sum(counts.get(letter, 0) for letter in letters)

        if difficulty not in {"상", "중", "하"}:
            difficulty = "상"
        scored_candidates = [
            (candidate, continuation_count(candidate)) for candidate in candidates
        ]
        if difficulty == "상":
            eligible = scored_candidates
        else:
            bounds = {"중": (11, 19), "하": (30, 50)}[difficulty]
            eligible = [
                item for item in scored_candidates
                if bounds[0] <= item[1] <= bounds[1]
            ]
            if not eligible:
                return None
            return random.choice(eligible)[0][0]
        return min(
            eligible,
            key=lambda item: (item[1], len(item[0][0]), item[0][0]),
        )[0][0]

    def random_start_word(self, minimum_next_words=30):
        candidates = self._read_rows(
            "SELECT word, last_letter FROM words WHERE length(word) = 2"
        )
        if not candidates:
            return None

        counts = dict(
            self._read_rows(
                "SELECT first_letter, COUNT(*) FROM words GROUP BY first_letter"
            )
        )
        eligible = []
        for word, last_letter in candidates:
            next_count = counts.get(last_letter, 0)
            next_count += sum(
                counts.get(letter, 0) for letter in dueum_candidates(last_letter)
            )
            if next_count >= minimum_next_words:
                eligible.append(word)
        return random.choice(eligible) if eligible else None

    def close(self):
        self.connection.close()