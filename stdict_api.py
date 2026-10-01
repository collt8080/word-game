import json
import os
import re
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    load_dotenv = getattr(import_module("dotenv"), "load_dotenv", None)
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(Path(__file__).with_name(".env"))


API_URL = "https://stdict.korean.go.kr/api/search.do"


class DictionaryApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class DictionaryEntry:
    word: str
    definition: str
    word_type: str
    part_of_speech: str
    link: str


def _comparable_word(word):
    return re.sub(r"[^가-힣ㄱ-ㅎㅏ-ㅣ]", "", word or "")


def _first(value):
    if isinstance(value, list):
        return value[0] if value else {}
    return value if isinstance(value, dict) else {}


def lookup_word(word, api_key=None):
    api_key = api_key or os.getenv("STDICT_API_KEY")
    if not api_key:
        raise DictionaryApiError("STDICT_API_KEY is not configured.")

    query = urlencode(
        {
            "key": api_key,
            "q": word,
            "req_type": "json",
            "method": "include",
            "type1": "word",
            "pos": "1",
            "num": "10",
        }
    )
    request = Request(
        f"{API_URL}?{query}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise DictionaryApiError(f"Dictionary API request failed: {error}") from error

    if "error" in payload:
        error = payload["error"]
        raise DictionaryApiError(
            f"Dictionary API error {error.get('error_code')}: {error.get('message')}"
        )

    items = payload.get("channel", {}).get("item", [])
    if isinstance(items, dict):
        items = [items]
    comparable_word = _comparable_word(word)
    exact_item = next(
        (
            item for item in items
            if _comparable_word(item.get("word")) == comparable_word
        ),
        None,
    )
    if exact_item is None:
        return None

    sense = _first(exact_item.get("sense"))
    return DictionaryEntry(
        word=exact_item.get("word", word),
        definition=sense.get("definition", "뜻풀이가 없습니다."),
        word_type=sense.get("type") or exact_item.get("type") or "일반어",
        part_of_speech=exact_item.get("pos", "명사"),
        link=sense.get("link", ""),
    )
