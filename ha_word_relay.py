import os
import re

from turso_word_chain import KoreanWordChain
from turso_word_chain.utils import normalize_player_word

from jev_api import JevApiError, is_definition_question, is_word_chain_acceptable
from stdict_api import DictionaryApiError, lookup_word
from word_store import TursoWordStore, dueum_candidates


def _format_chain_error(last_word, word):
    last_char = last_word[-1]
    dueum_chars = dueum_candidates(last_char)
    code = ord(last_char) - 0xAC00
    has_hangul = 0 <= code < 11172

    if dueum_chars:
        dueum_text = ", ".join(f"'{c}'" for c in dueum_chars)
        msg = f"'{last_word}'의 끝 글자 '{last_char}'나 {dueum_text}로 시작하는 말을 해 주세요."
        if has_hangul and code // 588 == 5:
            vowel = (code % 588) // 28
            trailing = code % 28
            wrong_ieung = chr(0xAC00 + (11 * 21 + vowel) * 28 + trailing)
            if word and word[0] == wrong_ieung:
                msg += f" 끝 글자 '{last_char}'는 '{dueum_chars[0]}'로도 이어져요. '{wrong_ieung}'로는 안 돼요."
    else:
        msg = f"'{last_word}'의 끝 글자 '{last_char}'로 시작하는 말을 해 주세요."
    return msg


def _extract_definition_word(user_input):
    if not isinstance(user_input, str):
        return None
    if not re.search(r"무슨\s*(?:말|뜻)", user_input):
        return None
    return _extract_definition_target(user_input)


def _extract_definition_target(user_input):
    if not isinstance(user_input, str):
        return ""
    marker = re.search(
        r"무슨\s*(?:말|뜻|의미|음식|간식|단어)"
        r"|(?:뭐|무엇|뭔)(?:야|예요|인가요|인지|니|데요|데|가요)?"
        r"|(?:뜻|의미)(?:이|은|가|을|를)?"
        r"(?:야|이에요|예요|인지|인가요)?",
        user_input,
    )
    if not marker:
        return ""

    words = re.findall(r"[가-힣]+", user_input[:marker.start()])
    particles = ("으로", "에서", "에게", "한테", "라는", "은", "는", "이", "가", "을", "를", "의", "도", "에", "로", "게")
    ignored_words = {
        "뜻", "의미", "말", "음식", "간식", "단어",
        "이거", "그거", "저거", "이것", "그것", "저것",
        "이게", "그게", "저게", "이건", "그건", "저건",
    }
    while words:
        word = words.pop()
        while True:
            for particle in particles:
                if word.endswith(particle) and len(word) > len(particle):
                    candidate = word[:-len(particle)]
                    if len(candidate) >= 2 or candidate in ignored_words:
                        word = candidate
                        break
            else:
                break
        if word in ignored_words:
            continue
        return word if len(word) >= 2 else ""
    return ""


class TursoWordRelayGame:
    def __init__(self, store=None, start_word=None, difficulty=None):
        self.store = store or TursoWordStore()
        self.store.initialize()
        self.difficulty = difficulty or os.getenv("WORD_GAME_DIFFICULTY", "하")
        try:
            self.max_mistakes = int(os.getenv("WORD_GAME_MAX_MISTAKES", "2").strip())
        except ValueError as error:
            raise ValueError("WORD_GAME_MAX_MISTAKES must be a non-negative integer.") from error
        if self.max_mistakes < 0:
            raise ValueError("WORD_GAME_MAX_MISTAKES must be a non-negative integer.")
        self.relay = KoreanWordChain(
            word_store=self.store,
            use_dueum=True,
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
            raise RuntimeError(
                f"시작 단어 '{selected_start_word}'가 DB에 없어 게임을 시작할 수 없습니다."
            )
        self.relay.reset_round()
        self.relay.remember_word(selected_start_word)
        self.last_word = selected_start_word
        self.active = True
        self.mistakes = 0
        return (
            f"끝말잇기 시작해요! 제가 먼저 '{selected_start_word}'라고 했어요. "
            f"이제 '{selected_start_word[-1]}'로 시작하는 낱말을 말해 주세요!"
        )

    def _mistake(self, message):
        if self.max_mistakes > 0:
            self.mistakes += 1
        if self.max_mistakes > 0 and self.mistakes >= self.max_mistakes:
            self.active = False
            return f"{message} 이번 판은 제가 이겼어요!", True
        return f"{message} 다시 말씀해 주세요.", False

    def _definition_reply(self, definition_word):
        definition_word = definition_word or self.last_word
        if not definition_word:
            return "뜻을 알고 싶은 낱말도 같이 말해 주세요.", False
        try:
            definition_entry = lookup_word(definition_word)
        except DictionaryApiError as error:
            if "STDICT_API_KEY is not configured" in str(error):
                return "사전 설정을 찾지 못했어요. 어른에게 알려 주세요.", False
            return "지금은 사전을 확인할 수 없어요. 잠시 뒤 다시 해봐요.", False
        if definition_entry is None:
            return f"국어사전에서 '{definition_word}'의 뜻을 찾지 못했어요.", False
        return (
            f"쉽게 말하면, '{definition_entry.word}'의 뜻은 이거예요: "
            f"{definition_entry.definition}",
            False,
        )

    def _try_definition_question(self, user_input):
        try:
            if not is_definition_question(user_input):
                return None
        except JevApiError:
            return None
        return self._definition_reply(_extract_definition_target(user_input))

    def submit(self, user_word):
        word = normalize_player_word(user_word)
        if word and any(
            stop_word in word for stop_word in ("없어", "졌어", "종료", "그만")
        ):
            self.active = False
            return "알겠어요. 게임을 여기서 끝낼게요!", True

        definition_word = _extract_definition_word(user_word)
        if definition_word is not None:
            return self._definition_reply(definition_word)

        if not word:
            definition_reply = self._try_definition_question(user_word)
            if definition_reply is not None:
                return definition_reply
            return self._mistake("두 글자 이상인 낱말을 말해 주세요.")
        if not self.relay.can_follow(self.last_word, word):
            definition_reply = self._try_definition_question(user_word)
            if definition_reply is not None:
                return definition_reply
            return self._mistake(_format_chain_error(self.last_word, word))
        if word in self.relay.history:
            definition_reply = self._try_definition_question(user_word)
            if definition_reply is not None:
                return definition_reply
            return self._mistake(f"'{word}'은(는) 아까 나왔어요.")
        dictionary_entry = None
        word_source = "db"
        store_unregistered_word = False
        if not self.store.contains(word):
            try:
                dictionary_entry = lookup_word(word)
            except DictionaryApiError as error:
                if "STDICT_API_KEY is not configured" in str(error):
                    return "사전 설정을 찾지 못했어요. 어른에게 알려 주세요.", False
                return "지금은 사전을 확인할 수 없어요. 잠시 뒤 다시 해봐요.", False
            if dictionary_entry is None:
                allow_unregistered = os.getenv(
                    "ALLOW_UNREGISTERED_WORDS", "false"
                ).strip().lower() in {"1", "true", "yes", "y"}
                if not allow_unregistered:
                    return self._mistake(f"'{word}'은(는) 사전에서 찾지 못했어요. 다른 낱말을 말해 볼까요?")
                try:
                    jev_decision = is_word_chain_acceptable(word)
                except JevApiError:
                    return "새 낱말을 확인할 수 없어요. 잠시 뒤 다시 해봐요.", False
                allow_dialect = os.getenv(
                    "ALLOW_DIALECT_WORDS", "false"
                ).strip().lower() in {"1", "true", "yes", "y"}
                if jev_decision.profane:
                    return self._mistake("그 말은 게임에서 쓰지 않기로 해요.")
                if jev_decision.dialect:
                    if not allow_dialect:
                        return self._mistake("그 방언은 이번 게임에서 쓸 수 없어요.")
                elif not jev_decision.acceptable:
                    return self._mistake("그 말은 끝말잇기 낱말로 쓰기 어려워요.")
                if not jev_decision.lexical_item:
                    return self._mistake("문장 말고 낱말 하나를 말해 주세요.")
                store_unregistered_word = (
                    not jev_decision.dialect
                    and jev_decision.noun
                    and os.getenv("STORE_JEV_APPROVED_WORDS", "false").strip().lower()
                    in {"1", "true", "yes", "y"}
                )
                word_source = "jev"
                if store_unregistered_word:
                    self.store.add_word(
                        word,
                        word_type="AI승인",
                        dictionary_registered=False,
                        registered_by="jev_ai",
                        notes=(
                            "Jev AI accepted at threshold "
                            f"{os.getenv('JEV_ACCEPT_THRESHOLD', '0.58').strip()}"
                        ),
                    )
            else:
                word_source = "dictionary"

        if dictionary_entry is not None:
            entry_category = dictionary_entry.word_type or ""
            if "비속어" in entry_category:
                return self._mistake("그 말은 게임에서 쓰지 않기로 해요.")
            if (
                dictionary_entry.part_of_speech == "명사"
                and "방언" not in entry_category
            ):
                self.store.add_word(
                    word,
                    word_type=entry_category,
                    dictionary_registered=True,
                    registered_by="stdict_api",
                    notes=dictionary_entry.definition,
                )
        self.relay.remember_word(word)
        source_messages = {
            "db": " 낱말 목록에서 찾았어요.",
            "dictionary": " 국어사전에서 찾았어요.",
            "jev": " 국어사전에는 없지만 AI가 낱말로 인정했어요.",
        }
        next_word = self.relay.choose_reply(word)
        if not next_word:
            self.active = False
            return (
                f"{word}!{source_messages[word_source]} "
                "제가 이을 말을 못 찾았어요. 당신이 이겼어요!",
                True,
            )

        self.last_word = next_word
        self.mistakes = 0
        return (
            f"{word}!{source_messages[word_source]} 제 말은 '{next_word}'예요. "
            f"'{next_word[-1]}'로 시작하는 말을 해 주세요.",
            False,
        )

    def close(self):
        self.store.close()


def _local_service(function):
    return function


service = globals().get("service", _local_service)


def _speak(message, speaker):
    ha_tts = globals().get("tts")
    if ha_tts is None:
        raise RuntimeError("TTS is only available inside Home Assistant.")
    ha_tts.speak(
        entity_id="tts.piper",
        media_player_entity_id=speaker,
        message=message,
    )


if "_word_relay_game" not in globals():
    _word_relay_game = None


@service
def manage_word_relay(user_word=None, difficulty=None, speaker=None):
    """yaml
        name: 한국어 끝말잇기
        description: 끝말잇기를 시작하거나 낱말을 제출하고 선택한 스피커로 답을 들려줍니다.
        fields:
            user_word:
                name: 입력 낱말
                description: 비워 두면 새 게임을 시작합니다.
                required: false
                selector:
                    text:
            difficulty:
                name: 난이도
                required: false
                selector:
                    select:
                        options:
                            - 상
                            - 중
                            - 하
            speaker:
                name: 스피커
                description: Piper 음성을 재생할 미디어 플레이어를 선택합니다.
                required: true
                selector:
                    entity:
                        filter:
                            - domain: media_player
    """
    global _word_relay_game
    if _word_relay_game is None:
        _word_relay_game = TursoWordRelayGame(difficulty=difficulty)
    elif difficulty is not None:
        _word_relay_game.set_difficulty(difficulty)
    if not _word_relay_game.active or user_word is None:
        message = _word_relay_game.start()
    else:
        message, _ = _word_relay_game.submit(user_word)
    _speak(message, speaker)


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