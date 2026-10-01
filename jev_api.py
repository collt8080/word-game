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
    lexical_item: bool


def is_word_chain_acceptable(word, api_key=None):
    api_key = api_key or os.getenv("JEV_API_KEY")
    if not api_key:
        raise JevApiError("JEV_API_KEY is not configured.")
    try:
        accept_threshold = float(os.getenv("JEV_ACCEPT_THRESHOLD", "0.6").strip())
    except ValueError as error:
        raise JevApiError("JEV_ACCEPT_THRESHOLD must be a number from 0 to 1.") from error
    if not 0 <= accept_threshold <= 1:
        raise JevApiError("JEV_ACCEPT_THRESHOLD must be a number from 0 to 1.")

    body = {
        "state": {
            "word": word,
            "context": "한국어 끝말잇기에서 사용할 단어를 판정합니다. 표준국어대사전에 아직 없어도 널리 쓰이는 과학·화학·기술 전문 용어는 단어일 수 있습니다. 지역 방언, 비표준 구어 표현, 문장과 활용형은 단어로 인정하지 않습니다.",
        },
        "model": "jev-latest",
        "questions": {
            "is_acceptable": {
                "type": "noul",
                "instructions": "이 입력이 한국어 끝말잇기에 사용할 수 있는 독립된 단어 또는 확립된 전문 용어입니까? 사전에 아직 등재되지 않은 과학·화학·기술 전문 용어는 인정할 수 있습니다. 오타, 무작위 문자열, 문장, 활용형, 지역 방언, 비표준 구어 표현은 거부하십시오. 비속어 여부는 이 항목에서 판단하지 마십시오.",
            },
            "is_profane": {
                "type": "noul",
                "instructions": "이 한국어 표현은 비속어, 욕설, 음란하거나 모욕적인 표현입니까? 해당하면 참으로 답하십시오.",
            },
            "is_dialect": {
                "type": "noul",
                "instructions": "이 표현은 표준어가 아니라 특정 지역에서 쓰는 방언이나 비표준 지역 표현입니까? 생소한 구어 표현이 지역 방언일 가능성이 있으면 참으로 판단하십시오. 사전에 정식 등재된 표준어 전문 용어는 방언이 아닙니다.",
            },
            "is_lexical_item": {
                "type": "noul",
                "instructions": "이 입력은 문장, 질문, 인사말, 구(phrase), 용언의 활용형이 아니라 독립된 단어 또는 굳어진 합성 전문 용어입니까? '습니까', '합니다', '했어요', '하세요' 같은 동사·형용사 어미로 끝나는 표현은 거짓으로 답하십시오.",
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
        acceptable = float(answers["is_acceptable"]["noul"]) >= accept_threshold
        profane = float(answers["is_profane"]["noul"]) >= 0.5
        dialect = float(answers["is_dialect"]["noul"]) >= 0.5
        lexical_item = float(answers["is_lexical_item"]["noul"]) >= 0.5
    except (KeyError, TypeError, ValueError) as error:
        raise JevApiError("Jev API returned an invalid decision.") from error
    return JevDecision(acceptable, profane, dialect, lexical_item)
