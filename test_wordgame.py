import sqlite3
import unittest

from word_store import TursoWordStore, dueum_candidates
from ha_word_relay import TursoWordRelayGame


class WordChainTests(unittest.TestCase):
    def setUp(self):
        self.store = TursoWordStore(sqlite3.connect(":memory:"))
        self.store.initialize()
        self.store.add_words(["사과", "과자", "자동차", "차표", "표범"])
        self.game = TursoWordRelayGame(self.store, start_word="사과")
        self.game.start()

    def tearDown(self):
        self.store.close()

    def test_player_and_computer_chain_words_from_database(self):
        message, game_over = self.game.submit("과자")
        self.assertFalse(game_over)
        self.assertIn("자동차", message)

        message, game_over = self.game.submit("차표")
        self.assertFalse(game_over)
        self.assertIn("표범", message)

    def test_computer_chooses_word_with_fewest_next_words(self):
        store = TursoWordStore(sqlite3.connect(":memory:"))
        store.initialize()
        store.add_words([
            "사과", "과자", "자동차", "자즙", "차수", "차량", "즙액",
        ])
        game = TursoWordRelayGame(store, start_word="사과")
        game.start()
        message, game_over = game.submit("과자")
        self.assertFalse(game_over)
        self.assertIn("자즙", message)
        store.close()

    def test_medium_and_easy_difficulty_skip_small_branch_counts(self):
        store = TursoWordStore(sqlite3.connect(":memory:"))
        store.initialize()
        store.add_words([
            "사과", "과자", "자동차", "자즙", "차수", "차량", "차림",
            "차례", "차도", "차표", "차장", "차돌", "차선", "차원", "차별", "즙액",
        ])
        self.assertEqual(
            store.next_word("자", ["사과", "과자"], difficulty="상"), "자즙"
        )
        self.assertEqual(
            store.next_word("자", ["사과", "과자"], difficulty="중"), "자동차"
        )
        self.assertEqual(
            store.next_word("자", ["사과", "과자"], difficulty="하"), "자동차"
        )
        store.close()

    def test_rejects_unknown_word(self):
        message, game_over = self.game.submit("과자아")
        self.assertTrue(game_over)
        self.assertIn("단어 목록에 없습니다", message)

    def test_applies_dueum_rule(self):
        self.assertEqual(dueum_candidates("력"), ["녁"])
        self.assertEqual(dueum_candidates("녀"), ["여"])

    def test_stores_word_metadata(self):
        self.store.add_word(
            "국어",
            dictionary_registered=True,
            registered_by="cline",
            notes="표준국어대사전 확인",
        )
        metadata = self.store.get_word("국어")
        self.assertEqual(metadata["word"], "국어")
        self.assertEqual(metadata["word_type"], "")
        self.assertTrue(metadata["dictionary_registered"])
        self.assertEqual(metadata["registered_by"], "cline")
        self.assertTrue(metadata["registered_at"])
        self.assertEqual(metadata["notes"], "표준국어대사전 확인")

    def test_migrates_old_words_table(self):
        connection = sqlite3.connect(":memory:")
        connection.execute(
            "CREATE TABLE words (word TEXT PRIMARY KEY, first_letter TEXT NOT NULL, last_letter TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO words VALUES ('사과', '사', '과')")
        connection.commit()
        migrated_store = TursoWordStore(connection)
        migrated_store.initialize()
        metadata = migrated_store.get_word("사과")
        self.assertFalse(metadata["dictionary_registered"])
        self.assertEqual(metadata["registered_at"], "")
        migrated_store.close()

    def test_import_updates_existing_word_metadata(self):
        self.store.add_word("사과")
        self.store.add_word(
            "사과",
            word_type="고유어",
            dictionary_registered=True,
            registered_by="json_import",
            notes="source: sample.json",
        )
        metadata = self.store.get_word("사과")
        self.assertEqual(metadata["word_type"], "고유어")
        self.assertTrue(metadata["dictionary_registered"])
        self.assertEqual(metadata["registered_by"], "json_import")

    def test_can_skip_existing_words(self):
        self.store.add_word("사과", word_type="고유어")
        imported = self.store.add_word_records(
            [{"word": "사과", "word_type": "한자어"}, {"word": "국어", "word_type": "한자어"}],
            skip_existing=True,
        )
        self.assertEqual(imported, 1)
        self.assertEqual(self.store.get_word("사과")["word_type"], "고유어")
        self.assertEqual(self.store.get_word("국어")["word_type"], "한자어")


if __name__ == "__main__":
    unittest.main()