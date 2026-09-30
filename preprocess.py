# import csv
# import re
# from korean_word_relay import preprocess_word

# RAW_DATA = 'raw_data/korean5800.csv'
# FORMED_DATA = 'korean_word_relay/data/korean5800.txt'

# word_set = {'사랑', '우정', '기쁨', '슬픔'}


# with open(RAW_DATA, 'r') as fr:
#     reader = csv.reader(fr)
#     for row in reader:
#         if row[2] in ['명', '부']:
#             word = preprocess_word(row[1])
#             if word:
#                 word_set.add(word)

# with open(FORMED_DATA, 'w') as fw:
#     data = '\n'.join(list(word_set))
#     fw.write(data)

import argparse
import json
from pathlib import Path
from time import sleep

from word_store import TursoWordStore, normalize_word


DEFAULT_SOURCE = Path(__file__).parent / "raw_data"
ALLOWED_WORD_TYPES = {"고유어", "한자어", "외래어"}


def read_json_records(source):
    with open(source, encoding="utf-8") as json_file:
        data = json.load(json_file)

    seen_words = set()
    for item in data.get("channel", {}).get("item", []):
        word_info = item.get("word_info", {})
        word = word_info.get("word", "")
        word_type = word_info.get("word_type")
        has_noun_pos = any(
            pos_info.get("pos") == "명사"
            for pos_info in word_info.get("pos_info", [])
        )
        normalized = normalize_word(word)
        if (
            word_info.get("word_unit") == "단어"
            and has_noun_pos
            and word_type in ALLOWED_WORD_TYPES
            and normalized
            and normalized not in seen_words
        ):
            seen_words.add(normalized)
            yield {"word": normalized, "word_type": word_type}


def main():
    parser = argparse.ArgumentParser(description="Import filtered JSON words into Turso.")
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    args = parser.parse_args()
    if args.batch_size < 1 or args.delay < 0 or args.retries < 0 or args.retry_delay < 0:
        parser.error("batch-size must be positive; delays and retries cannot be negative")

    store = TursoWordStore()
    try:
        store.initialize()
        sources = sorted(args.source.glob("*.json")) if args.source.is_dir() else [args.source]
        total = 0
        for file_number, source in enumerate(sources, start=1):
            records = list(read_json_records(source))
            batch_total = (len(records) + args.batch_size - 1) // args.batch_size
            print(
                f"[{file_number}/{len(sources)}] {source.name}: "
                f"{len(records)}개, {batch_total}개 배치 업로드 시작",
                flush=True,
            )

            def report_progress(batch_number, total_batches):
                print(
                    f"[{file_number}/{len(sources)}] {source.name}: "
                    f"배치 {batch_number}/{total_batches} 완료",
                    flush=True,
                )

            imported = store.add_word_records(
                records,
                registered_by="json_import",
                dictionary_registered=True,
                notes=f"source: {source.name}",
                batch_size=args.batch_size,
                progress=report_progress,
                retries=args.retries,
                retry_delay=args.retry_delay,
                skip_existing=True,
            )
            total += imported
            print(
                f"[{file_number}/{len(sources)}] {source.name}: "
                f"{imported}개 처리, 누적 {total}개",
                flush=True,
            )
            if args.delay:
                sleep(args.delay)
        store.add_word("사과", registered_by="preprocess")
        print(f"완료: 총 {total}개 단어를 Turso에 등록했습니다.")
    finally:
        store.close()


if __name__ == "__main__":
    main()

