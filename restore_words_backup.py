from word_store import TursoWordStore

store = TursoWordStore()
try:
    store.connection.execute("DROP TABLE IF EXISTS words")
    store.connection.execute("ALTER TABLE words_bak RENAME TO words")
    store.connection.commit()
    print("Restored words from words_bak.")
finally:
    store.close()
