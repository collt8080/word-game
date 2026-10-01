# 한국어 끝말잇기 (Home Assistant & 로컬 연동)

Turso DB 및 국립국어원 표준국어대사전 Open API, TypeSafe Jev AI를 연동한 한국어 끝말잇기 게임입니다.  
Home Assistant(Pyscript) 음성 게임과 로컬 터미널 테스트를 모두 지원합니다.

---

## 주요 기능
- **Turso Cloud DB 기반**: 파일 대신 클라우드 DB의 단어를 조회하여 끝말잇기 진행
- **두음법칙 완벽 지원**: `ㄹ → ㄴ`, `ㄹ → ㅇ`, `ㄴ → ㅇ` 등 두음법칙 자동 계산
- **난이도 조절 (상 / 중 / 하)**:
  - **상**: 컴퓨터가 다음 이어질 단어 수가 가장 적은 단어(공격적)를 우선 선택 (동률 시 짧은 글자 우선)
  - **중**: 다음 이어질 단어 수가 11~19개인 단어 중 랜덤 선택
  - **하**: 다음 이어질 단어 수가 30~50개인 단어 중 랜덤 선택 (해당 범위 없으면 플레이어 승리)
- **랜덤 시작 단어**: DB에서 다음 이어갈 수 있는 단어가 30개 이상인 2글자 단어로 매 판 자동 시작
- **표준국어대사전 Open API 연동**: DB에 없는 단어를 플레이어가 입력 시 국립국어원 API로 실시간 검증 후 DB 자동 등록
- **Jev AI 미등재어/신조어 판정**:
  - 국어사전에 없더라도 화학물질, 전문용어 등 사회 통념상 허용할 단어인지 Jev AI로 판정 (60% 이상 찬성 시 허용 및 `dictionary_registered=0` 등록)
  - **비속어는 무조건 차단**
  - **방언은 옵션(`ALLOW_DIALECT_WORDS`)으로 게임 사용 여부를 제어**하지만, 방언은 DB에 저장하지 않음
  - **DB에는 명사만 등록**: Jev 승인 단어도 명사 판정을 통과해야 저장하며, 시작 단어는 기존 DB에서만 선택
- **2회 기회 규칙**: 한 턴에 한 번 틀리면 다시 기회를 주고, 정상적으로 턴이 넘어가면 실수 횟수를 초기화합니다. 같은 턴에서 두 번 틀리면 패배합니다.
- **등록 출처별 안내**: DB 단어, 표준국어대사전 확인 단어, Jev AI 승인 단어에 서로 다른 짧은 응답을 합니다.

---

## 설치 및 준비

### 1. 파이썬 의존성 설치
```powershell
pip install -r requirements.txt
```

### 2. 환경변수 설정 (`.env`)
프로젝트 루트 폴더에 `.env` 파일을 만들고 아래 정보를 입력합니다.
```env
# Turso Cloud DB 접속 정보 (필수)
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your-turso-token

# 게임 기본 난이도 (상 / 중 / 하, 기본값: 하)
WORD_GAME_DIFFICULTY=하

# 국립국어원 표준국어대사전 Open API 키 (선택/권장)
STDICT_API_KEY=your-stdict-api-key

# Jev AI (TypeSafe) 미등재어 판정 설정 (선택)
ALLOW_UNREGISTERED_WORDS=true
JEV_API_KEY=your-jev-api-key
ALLOW_DIALECT_WORDS=false
JEV_ACCEPT_THRESHOLD=0.6
STORE_JEV_APPROVED_WORDS=false
```

`JEV_ACCEPT_THRESHOLD`는 미등재 단어 허용 점수 기준(0~1)이며 기본값은 0.6입니다.
`STORE_JEV_APPROVED_WORDS`가 `false`이면 Jev가 허용한 단어도 DB에 저장하지 않습니다.

---

## 실행 방법

### 로컬 터미널에서 실행
```powershell
python .\ha_word_relay.py
```
- 단어를 입력하며 대화형으로 게임을 진행합니다.
- `q`를 입력하면 게임이 종료됩니다.

### Home Assistant (Pyscript) 연동
1. Home Assistant의 `config/pyscript/` 디렉토리에 아래 파일들을 복사합니다:
   - `ha_word_relay.py`
   - `word_store.py`
   - `stdict_api.py`
   - `jev_api.py`
   - `korean_word_relay/` 폴더 전체
2. HA Pyscript 환경에 `turso_serverless`, `hgtk`, `six`, `python-dotenv` 패키지가 설치되어 있어야 합니다.
3. `ha_word_relay.py` 상단의 TTS 엔진 및 스피커 엔티티 ID를 본인 환경에 맞게 수정합니다:
   - `entity_id="tts.piper"`
   - `media_player_entity_id="media_player.your_speaker"`
4. HA 자동화 또는 개발자 도구의 서비스에서 호출:
   ```yaml
   service: pyscript.manage_word_relay
   data:
     user_word: "사과"
     difficulty: "중" # 생략 시 .env 기본값 사용
   ```

---

## 데이터베이스 구조 (`words` 테이블)

| 컬럼명 | 타입 | 설명 |
| --- | --- | --- |
| `word` | TEXT | 정규화된 한글 단어 (Primary Key) |
| `first_letter` | TEXT | 첫 글자 (조회 인덱스) |
| `last_letter` | TEXT | 끝 글자 |
| `word_type` | TEXT | 단어 종류 (고유어, 한자어, 외래어, AI승인 등) |
| `dictionary_registered` | INTEGER | 국어사전 등재 여부 (1: 등재, 0: 미등재/AI허용) |
| `registered_by` | TEXT | 등록 출처 (`csv_import`, `stdict_api`, `jev_ai` 등) |
| `registered_at` | TEXT | 등록 일시 (UTC) |
| `notes` | TEXT | 뜻풀이 또는 비고 |

---

## DB 백업
현재 `words` 테이블을 `words_bak` 테이블로 복사해두려면:
```powershell
python .\backup_words.py
```


