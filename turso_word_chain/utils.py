import re


def normalize_player_word(word):
    if not word:
        return None
    normalized = re.sub(r"\d", "", re.sub(r"\W+", "", word.strip()))
    return normalized if len(normalized) >= 2 else None