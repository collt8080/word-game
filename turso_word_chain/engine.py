from word_store import dueum_candidates, normalize_word

from .utils import normalize_player_word


class KoreanWordChain:
    def __init__(self, word_store, use_dueum=True, difficulty="상"):
        if word_store is None:
            raise ValueError("A word database store is required.")
        self.word_store = word_store
        self.use_dueum = use_dueum
        self.difficulty = difficulty
        self.history = []

    def remember_word(self, word):
        normalized = normalize_player_word(word)
        if not normalized or normalized in self.history:
            return False
        self.history.append(normalized)
        return True

    def reset_round(self):
        self.history.clear()

    def can_follow(self, previous_word, next_word):
        next_word = normalize_player_word(next_word)
        if not previous_word or not next_word:
            return False

        last_letter = previous_word.strip()[-1]
        if next_word[0] == last_letter:
            return True
        return self.use_dueum and next_word[0] in dueum_candidates(last_letter)

    def choose_reply(self, word):
        normalized = normalize_word(word)
        if not normalized:
            return None
        reply = self.word_store.next_word(
            normalized[-1],
            self.history,
            use_dueum=self.use_dueum,
            difficulty=self.difficulty,
        )
        if reply:
            self.remember_word(reply)
        return reply