# korean-word-relay
### 끝말잇기 package for python 
* 한국어 낱말 게임 끝말잇기를 쉽게 커스터마이징 할 수 있는 패키지
* 모델이 사용할 끝말잇기 단어 직접 선택 (난이도 조절 가능)
* 두음법칙 적용 (여부 선택)
* 이전 단어와 이어지지 않거나 이미 나왔던 단어 입력시 패배


## Installation
Using `pip`:
```
pip install korean-word-relay
```

## Usage
### Quick Start
```python
from korean_word_relay import WordRelay

word_relay = WordRelay()
word_relay.play()
```
### result
```
--------------끝말잇기----------------
시작 단어: 파이썬
<< 썬샤인
>> 인간
<< 간택
>> 택시
<< 시리
>> 리그
<< 그대
>> 대략
<< 약관
>> 관람
<< 람보
>> 보도
<< 도로묵
------------------------------
no word to answer
YOU WIN!
```
<hr/>

### Default optional parameter
```python
word_relay = WordRelay(import_default=True, words_path=None, use_dueum=True, debug_print=True):
)
```
- import_default(boolean): If True, import candidates of korean words from ['자주 쓰이는 한국어 낱말 모음 5800'](https://ko.wiktionary.org/wiki/%EB%B6%80%EB%A1%9D:%EC%9E%90%EC%A3%BC_%EC%93%B0%EC%9D%B4%EB%8A%94_%ED%95%9C%EA%B5%AD%EC%96%B4_%EB%82%B1%EB%A7%90_5800)
- `words_path(None|string)`: If given path(.txt), import candidates of words list from txt file
- `use_dueum(boolean)`: If True, 두음법칙 is allowed
- `debug_print(boolean)`: If True, print warning message on console

### Example format for words_path
`words_path` should be `None` or **list of korean words in txt extension**. For instance, `word_list.txt` should be
```
사랑
우정
믿음
.
.
여자친구
```
If you want to make game much difficult, get `killing_words.txt` from [here](https://github.com/5yearsKim/korean_word_relay/blob/main/raw_data/killing_words.txt).

<hr/>

###  Methods of WordRelay

```python
word_relay = WordRelay()

# 주어진 낱말에 이어지는 단어 리턴
# set log_history=False if you don't want to add word in history
next_word = word_relay.get_next('성질') # next_word is None or 질X (예: 질문)

# 두 낱말이 이어지는지 여부 체크
is_continue = word_relay.check_continue('질문', '문지기') # is_continue == True

# 특정 낱말을 이미 나온말(history)에 추가
word_relay.add_history('문지기')
print(word_relay.history) # word_relay.history = ['질문', '문지기'], 질문 was added get_next above

# history 를 초기화
word_relay.reset()
print(word_relay.history) # word_relay.history = []
```

## etc
Checking whether word is valid or not is not implemented in this project, since 1. criteria for *valid language* is keep changing, 2. including korean dictionary can make this package too big. You can implement your own code to check whether word is valid or not.

## Turso-backed Home Assistant and local game

The root-level `wordgame.py` uses Turso as its word source. It checks that
player words exist, rejects repeats and invalid chains, and chooses the next
computer word from the database. No word-list file is read during gameplay.

Create a Turso database and auth token, then set these environment variables in
the shell where the importer or local game will run:

```powershell
$env:TURSO_DATABASE_URL = "your Turso database URL"
$env:TURSO_AUTH_TOKEN = "your Turso auth token"
python -m pip install -r requirements.txt
python .\preprocess.py
python .\wordgame.py
```

The `words` table has these columns:

| Column | Meaning |
| --- | --- |
| `word` | Normalized Korean word, primary key |
| `first_letter` / `last_letter` | Letters used for chain lookup |
| `dictionary_registered` | `0` or `1`; default is `0` until verified |
| `registered_by` | Cline, user, importer, or another identifier |
| `registered_at` | UTC database timestamp at first registration |
| `notes` | Other information |

For example, after connecting the Turso MCP in Cline, the equivalent SQL for
registering a verified word is:

```sql
UPDATE words
SET dictionary_registered = 1,
	registered_by = 'cline',
	notes = '표준국어대사전 확인'
WHERE word = '사과';
```

The game currently uses all words in the `words` table and treats
`dictionary_registered` as metadata. This avoids making the game unusable when
the imported list has not been reviewed yet. The `get_word()` and
`set_dictionary_status()` methods in `word_store.py` are available for an MCP
관리 script or future dictionary-only mode.

Difficulty is configured with `WORD_GAME_DIFFICULTY` or the HA service's
`difficulty` field:

- `상`: choose the candidate with the fewest next words.
- `중`: choose randomly among candidates with 4-6 next words.
- `하`: choose randomly among candidates with 11-13 next words.

If a requested range has no candidates, the computer has no valid response and
the player wins that round. It does not select a word outside the requested
range.
`preprocess.py` imports every `.json` file in `raw_data` into Turso and adds the
game's starting word. It keeps only entries where `word_unit` is `단어`, a
`pos_info` item has `pos` equal to `명사`, `word_type` is one of `고유어`,
`한자어`, or `외래어`, and the word contains only Korean syllables. Each file is
sent in batches of 100 records, with a small delay between files:

```powershell
python .\preprocess.py --batch-size 100 --delay 0.2
```

The JSON entries are marked as dictionary-registered, with `word_type` stored in
its own column. The source filename is saved in `notes`. Gameplay reads words
from Turso after the import.

To create a CSV without connecting to Turso:

```powershell
python .\export_words_csv.py -o .\words_import.csv
```

The CSV uses the same filters and normalization rules as the importer. For an
existing database, import it into a temporary table first, then insert only new
words so the existing `words` rows are preserved:

```sql
CREATE TABLE words_import AS SELECT * FROM words WHERE 0;
```

After importing `words_import.csv` into that temporary table:

```sql
INSERT OR IGNORE INTO words
SELECT * FROM words_import;
DROP TABLE words_import;
```

Or let the project script import the CSV into the existing `words` table:

```powershell
python .\import_csv_to_turso.py .\words_import.csv --batch-size 100
```

Existing words are skipped and only new words are inserted. The script does not
rename, delete, or modify `words_bak`.

For Home Assistant Pyscript, place `wordgame.py` and `word_store.py` in the
Pyscript scripts directory, install `turso_serverless` in the Pyscript Python
environment, and provide `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` to Home
Assistant. Update the TTS and media-player entity IDs in `wordgame.py` to match
your setup.

When a player word is not in Turso, `ha_word_relay.py` checks the Standard
Korean Language Dictionary API. Add its key only to the local `.env` file:

```env
STDICT_API_KEY=your-stdict-api-key
```

An exact noun match is saved to Turso with its definition, type, and dictionary
link, but those details are not spoken during the game. If the API is
unavailable, the game asks the player to retry instead of treating the word as a
loss.

The VS Code MCP configuration in `.vscode/mcp.json` connects to Turso Cloud's
official MCP server. Authorize it through the OAuth prompt in VS Code. This MCP
connection manages Turso Cloud; the game itself connects with the database URL
and token above.


