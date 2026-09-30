from word_store import TursoWordStore

store = TursoWordStore()
try:
    store.initialize()
    rows = store._read_rows(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("words",),
    )
    print("words table initialized:", bool(rows))
finally:
    store.close()
