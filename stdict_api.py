import json
import os
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


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
            "method": "exact",
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
    exact_item = next((item for item in items if item.get("word") == word), None)
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
