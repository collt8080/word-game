from word_store import TursoWordStore

def backup_words():
    store = TursoWordStore()
    try:
        tables = [r[0] for r in store._read_rows("SELECT name FROM sqlite_master WHERE type='table'")]
        print("현재 DB 테이블 목록:", tables)

        if "words" not in tables:
            print("오류: 'words' 테이블이 존재하지 않습니다.")
            return

        words_count = store._read_rows("SELECT COUNT(*) FROM words")[0][0]
        print(f"현재 'words' 테이블 행 수: {words_count}")

        # 기존 words_bak, word_bak 정리
        for bak_name in ["words_bak", "word_bak"]:
            if bak_name in tables:
                print(f"기존 '{bak_name}' 테이블 삭제 중...")
                store.connection.execute(f"DROP TABLE IF EXISTS {bak_name}")

        # 복사: words -> words_bak
        print("'words' 테이블을 'words_bak'으로 복사 중...")
        store.connection.execute("CREATE TABLE words_bak AS SELECT * FROM words")
        store.connection.commit()

        bak_count = store._read_rows("SELECT COUNT(*) FROM words_bak")[0][0]
        print(f"복사 완료! 'words_bak' 테이블 행 수: {bak_count}")

        final_tables = [r[0] for r in store._read_rows("SELECT name FROM sqlite_master WHERE type='table'")]
        print("최종 DB 테이블 목록:", final_tables)
    finally:
        store.close()

if __name__ == "__main__":
    backup_words()
