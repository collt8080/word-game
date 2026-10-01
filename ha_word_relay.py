import os

from korean_word_relay import WordRelay
from korean_word_relay.utils import preprocess_word

from jev_api import JevApiError, is_word_chain_acceptable
from stdict_api import DictionaryApiError, lookup_word
from word_store import TursoWordStore, dueum_candidates


def _format_chain_error(last_word, word):
    last_char = last_word[-1]
    dueum_chars = dueum_candidates(last_char)

    def _josa_ro(char):
        code = ord(char) - 0xAC00
        return "로" if 0 <= code < 11172 and code % 28 in (0, 8) else "으로"

    def _josa_eun(char):
        code = ord(char) - 0xAC00
        return "은" if 0 <= code < 11172 and code % 28 != 0 else "는"

    code = ord(last_char) - 0xAC00
    has_hangul = 0 <= code < 11172

    if dueum_chars:
        dueum_text = ", ".join(f"'{c}'" for c in dueum_chars)
        msg = f"'{last_word}' 다음에는 '{last_char}' 또는 두음법칙에 따라 {dueum_text}{_josa_ro(dueum_chars[-1])} 시작해야 합니다."
        if has_hangul and code // 588 == 5:
            vowel = (code % 588) // 28
            trailing = code % 28
            wrong_ieung = chr(0xAC00 + (11 * 21 + vowel) * 28 + trailing)
            if word and word[0] == wrong_ieung:
                msg += f" (참고: '{last_char}'{_josa_eun(last_char)} 두음법칙상 '{dueum_chars[0]}'{_josa_ro(dueum_chars[0])}만 바뀌며 '{wrong_ieung}'{_josa_ro(wrong_ieung)}는 바뀌지 않습니다.)"
    else:
        msg = f"'{last_word}' 다음에는 '{last_char}'{_josa_ro(last_char)} 시작해야 합니다."
        if has_hangul and code // 588 in (2, 5):
            vowel = (code % 588) // 28
            trailing = code % 28
            wrong_ieung = chr(0xAC00 + (11 * 21 + vowel) * 28 + trailing)
            if word and word[0] == wrong_ieung:
                msg += f" (참고: '{last_char}'{_josa_eun(last_char)} 두음법칙상 '{wrong_ieung}'{_josa_ro(wrong_ieung)} 바뀌지 않습니다.)"
    return msg


class TursoWordRelayGame:
    def __init__(self, store=None, start_word=None, difficulty=None):
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
        self.mistakes = 0

    def set_difficulty(self, difficulty):
        if difficulty not in {"상", "중", "하"}:
            raise ValueError("difficulty must be one of: 상, 중, 하")
        self.difficulty = difficulty
        self.relay.difficulty = difficulty

    def start(self):
        selected_start_word = self.start_word or self.store.random_start_word()
        if selected_start_word is None:
            raise RuntimeError(
                "DB에 다음 단어가 30개 이상인 두 글자 시작 단어가 없습니다."
            )
        if not self.store.contains(selected_start_word):
            self.store.add_word(
                selected_start_word,
                registered_by="game_start",
                notes="게임 시작 단어",
            )
        self.relay.reset()
        self.relay.add_history(selected_start_word)
        self.last_word = selected_start_word
        self.active = True
        self.mistakes = 0
        return (
            f"끝말잇기를 시작합니다. 제 단어는 {selected_start_word}입니다. "
            f"'{selected_start_word[-1]}'(으)로 시작하는 단어를 말씀해 주세요."
        )

    def _mistake(self, message):
        self.mistakes += 1
        if self.mistakes >= 2:
            self.active = False
            return f"{message} 두 번 틀렸습니다. 제가 이겼습니다!", True
        return f"{message} 한 번 틀렸습니다. 다시 시도해 주세요.", False

    def submit(self, user_word):
        word = preprocess_word(user_word)
        if not word:
            return self._mistake("두 글자 이상의 단어를 입력해 주세요.")
        if not self.relay.check_continue(self.last_word, word):
            return self._mistake(_format_chain_error(self.last_word, word))
        if word in self.relay.history:
            return self._mistake(f"{word}은(는) 이미 사용한 단어입니다.")
        dictionary_entry = None
        store_unregistered_word = False
        if not self.store.contains(word):
            try:
                dictionary_entry = lookup_word(word)
            except DictionaryApiError as error:
                if "STDICT_API_KEY is not configured" in str(error):
                    return f"{word}은(는) DB에 없습니다. Home Assistant에 STDICT_API_KEY 설정이 필요합니다.", False
                return f"{word}은(는) DB에 없습니다. 표준국어대사전 API 연결에 실패했습니다. 네트워크나 API 상태를 확인한 뒤 다시 시도해 주세요.", False
            if dictionary_entry is None:
                allow_unregistered = os.getenv(
                    "ALLOW_UNREGISTERED_WORDS", "false"
                ).lower() in {"1", "true", "yes", "y"}
                if not allow_unregistered:
                    return self._mistake(f"{word}은(는) DB와 표준국어대사전에 없습니다.")
                try:
                    jev_decision = is_word_chain_acceptable(word)
                except JevApiError:
                    return f"{word}은(는) DB에 없습니다. Jev AI를 확인할 수 없으니 다시 시도해 주세요.", False
                allow_dialect = os.getenv(
                    "ALLOW_DIALECT_WORDS", "false"
                ).lower() in {"1", "true", "yes", "y"}
                if jev_decision.profane:
                    return self._mistake(f"{word}은(는) 비속어라서 사용할 수 없습니다.")
                if jev_decision.dialect:
                    if not allow_dialect:
                        return self._mistake(f"{word}은(는) 방언이라서 사용할 수 없습니다.")
                    store_unregistered_word = False
                else:
                    store_unregistered_word = True
                if not jev_decision.lexical_item:
                    return self._mistake(f"{word}은(는) 문장이나 활용형이라 끝말잇기 단어로 사용할 수 없습니다.")
                if not jev_decision.acceptable:
                    return self._mistake(f"{word}은(는) 끝말잇기에 사용할 수 없는 단어입니다.")
                if store_unregistered_word:
                    self.store.add_word(
                        word,
                        word_type="AI승인",
                        dictionary_registered=False,
                        registered_by="jev_ai",
                        notes="Jev AI acceptable probability >= 0.5",
                    )

        if dictionary_entry is not None:
            self.store.add_word(
                word,
                word_type=dictionary_entry.word_type,
                dictionary_registered=True,
                registered_by="stdict_api",
                notes=dictionary_entry.definition,
            )
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