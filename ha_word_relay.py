import os

from korean_word_relay import WordRelay
from korean_word_relay.utils import preprocess_word

from word_store import TursoWordStore


class TursoWordRelayGame:
    def __init__(self, store=None, start_word="조각", difficulty=None):
        self.store = store or TursoWordStore()
        self.store.initialize()
        self.difficulty = difficulty or os.getenv("WORD_GAME_DIFFICULTY", "상")
        self.relay = WordRelay(
            import_default=False,
            use_dueum=True,
            debug_print=False,
            word_store=self.store,
            difficulty=self.difficulty,
        )
        self.start_word = start_word
        self.last_word = ""
        self.active = False

    def set_difficulty(self, difficulty):
        if difficulty not in {"상", "중", "하"}:
            raise ValueError("difficulty must be one of: 상, 중, 하")
        self.difficulty = difficulty
        self.relay.difficulty = difficulty

    def start(self):
        if not self.store.contains(self.start_word):
            self.store.add_word(
                self.start_word,
                registered_by="game_start",
                notes="게임 시작 단어",
            )
        self.relay.reset()
        self.relay.add_history(self.start_word)
        self.last_word = self.start_word
        self.active = True
        return (
            f"끝말잇기를 시작합니다. 제 단어는 {self.start_word}입니다. "
            f"'{self.start_word[-1]}'(으)로 시작하는 단어를 말씀해 주세요."
        )

    def submit(self, user_word):
        word = preprocess_word(user_word)
        if not word:
            return "두 글자 이상의 단어를 입력해 주세요.", False
        if word in self.relay.history:
            self.active = False
            return f"{word}은(는) 이미 사용한 단어입니다. 제가 이겼습니다!", True
        if not self.store.contains(word):
            self.active = False
            return f"{word}은(는) 단어 목록에 없습니다. 제가 이겼습니다!", True
        if not self.relay.check_continue(self.last_word, word):
            self.active = False
            return f"{self.last_word} 다음에는 {word}을(를) 말할 수 없습니다. 제가 이겼습니다!", True

        self.relay.add_history(word)
        next_word = self.relay.get_next(word)
        if not next_word:
            self.active = False
            return f"{word}! 제가 이어갈 단어가 없네요. 당신이 이겼습니다!", True

        self.last_word = next_word
        return f"{word}! 제 단어는 {next_word}입니다. '{next_word[-1]}'(으)로 시작해 주세요.", False

    def close(self):
        self.store.close()


def _local_service(function):
    return function


service = globals().get("service", _local_service)


def _speak(message):
    ha_tts = globals().get("tts")
    if ha_tts is None:
        raise RuntimeError("TTS is only available inside Home Assistant.")
    ha_tts.speak(
        entity_id="tts.piper",
        media_player_entity_id="media_player.your_speaker",
        message=message,
    )


if "_word_relay_game" not in globals():
    _word_relay_game = None


@service
def manage_word_relay(user_word=None, difficulty=None):
    global _word_relay_game
    if _word_relay_game is None:
        _word_relay_game = TursoWordRelayGame(difficulty=difficulty)
    elif difficulty is not None:
        _word_relay_game.set_difficulty(difficulty)
    if not _word_relay_game.active or user_word is None:
        message = _word_relay_game.start()
    else:
        message, _ = _word_relay_game.submit(user_word)
    _speak(message)


def run_local_game():
    game = TursoWordRelayGame()
    try:
        print(game.start())
        while game.active:
            user_word = input("<< ").strip()
            if user_word.lower() == "q":
                print("게임을 종료합니다.")
                return
            message, _ = game.submit(user_word)
            print(message)
    except (RuntimeError, OSError) as error:
        print(f"게임을 시작할 수 없습니다: {error}")
    finally:
        game.close()


if __name__ == "__main__":
    run_local_game()