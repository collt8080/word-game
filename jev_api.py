import json
import os
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from urllib.request import Request, urlopen

try:
    load_dotenv = getattr(import_module("dotenv"), "load_dotenv", None)
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(Path(__file__).with_name(".env"))


API_URL = "https://api.typesafe.ai/v1/systemone"


class JevApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class JevDecision:
    acceptable: bool
    profane: bool
    dialect: bool


def is_word_chain_acceptable(word, api_key=None):
    api_key = api_key or os.getenv("JEV_API_KEY")
    if not api_key:
        raise JevApiError("JEV_API_KEY is not configured.")

    body = {
        "state": {
            "word": word,
            "context": "Korean word-chain game. The word may be a technical term, scientific term, product name, or commonly used term even if it is not in the Standard Korean Language Dictionary.",
        },
        "model": "jev-latest",
        "questions": {
            "is_acceptable": {
                "type": "noul",
                "instructions": "Would Korean speakers reasonably accept this as a usable word or established term in a social Korean word-chain game? Return true for established technical, scientific, product, or commonly used terms; return false for typos, random strings, or clearly invalid forms. Do not use this field to decide profanity or dialect.",
            },
            "is_profane": {
                "type": "noul",
                "instructions": "Is this Korean word vulgar, obscene, abusive, or profanity?",
            },
            "is_dialect": {
                "type": "noul",
                "instructions": "Is this word primarily a Korean regional dialect or dialectal expression rather than standard Korean?",
            },
        },
    }
    request = Request(
        API_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise JevApiError(f"Jev API request failed: {error}") from error

    try:
        answers = payload["answers"]
        acceptable = float(answers["is_acceptable"]["noul"]) >= 0.5
        profane = float(answers["is_profane"]["noul"]) >= 0.5
        dialect = float(answers["is_dialect"]["noul"]) >= 0.5
    except (KeyError, TypeError, ValueError) as error:
        raise JevApiError("Jev API returned an invalid decision.") from error
    return JevDecision(acceptable, profane, dialect)
