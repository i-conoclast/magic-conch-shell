# magic-conch-shell

> "The shell has spoken."

당신의 라이프·커리어 맥락을 스스로 축적하는 개인 메모리 + 에이전트 시스템.
가벼운 질문엔 소라고둥처럼, 진지한 질문엔 선택지와 근거로 답한다.

<!-- TODO: demo.gif — capture → KR auto-increment → okr show 5초 데모 -->

---

## 3 Beliefs

1. **Planning is a conversation, not a command.**
2. **Past you, present you, five-minutes-ago you — all in the shell.**
3. **Answer with data, or answer with nothing.**

---

## 핵심 원칙

- **사용자 outcome 중심** — 성공 기준은 시스템 체크가 아닌 사용자 변화.
- **침입성 낮게** — 잔소리·누락 감지 금지. 능동 개입은 스케줄 + 외부 시그널만.
- **마크다운 SSoT** — 모든 user data는 `brain/` 평문 마크다운. 캐시는 언제든 재빌드.

---

## 무엇을 할 수 있나

### 📝 캡처 & 검색
자유 메모(`mcs capture`)와 템플릿 기록(`mcs log`)으로 brain/ 에 마크다운을 쌓고,
하이브리드 검색(Milvus 벡터 + bge-m3 + 키워드)으로 즉시 꺼내 쓴다.
외부 에디터로 `brain/` 안에 그냥 저장만 해도 watcher 가 frontmatter를 자동 보충한다.

```bash
mcs capture "anthropic 1차 라운드 정리" -d career -e people/jane-smith
mcs search "면접" -d career --json
```

<img src="docs/images/readme/search-result.png" width="720" alt="mcs search 결과 — 하이브리드 검색 + 엔티티 후처리">
<!-- TODO 스크린샷: mcs search 컬러판 결과 화면 -->

### 🎯 OKR & 동적 KR 에이전트
`mcs okr new` 가 Hermes okr-intake 스킬로 대화형 인테이크를 돌리고,
저장된 각 KR 마다 `skills/objectives/<kr-id>/SKILL.md` 를 자동 생성한다.
이후 캡처에 `--kr` 만 붙이면 진척이 자동 증가하고 target 도달 시 achieved 로 전이.

```bash
mcs okr new "커리어 OKR 하나 세우자"
mcs capture "mock interview 2회" --kr 2026-Q2-career-mle-role.kr-2 --increment 2
mcs okr show 2026-Q2-career-mle-role
```

<img src="docs/images/readme/okr-show.png" width="720" alt="mcs okr show — KR 진척률 테이블">
<!-- TODO 스크린샷: mcs okr show 의 Rich 테이블 + KR 진척률 -->

### 📥 Inbox & 승격 (FR-G3)
엔티티 후보 / 스킬 후보 / 캡처 분류 등 "사람 판단 필요" 항목이 generic inbox 로 모인다.
`mcs inbox approve/defer/reject` 로 한 곳에서 처리한다.

```bash
mcs inbox list
mcs inbox approve <id>
mcs skill propose            # 스킬 승격 후보 추가
mcs entity merge <from> <into>
```

### 🤖 일과 루틴
Hermes 스킬이 brain 데이터를 컨텍스트로 받아 아침·낮·저녁 루틴을 돌린다.

```bash
mcs brief                    # morning-brief 스킬
mcs day 2026-05-19           # 일일 저널 뷰
mcs retro <phase>            # evening-retro — Phase B 에서 inbox-approve 연동
```

### 🩺 운영
환경 헬스체크와 풀 재빌드는 한 명령으로.

```bash
mcs doctor                   # 데몬·Ollama·Milvus·Notion 토큰 한 번에 점검
mcs reindex                  # 벡터 + 엔티티 백링크 재빌드
mcs daemon start --daemon    # MCP HTTP 서버 (:18342)
```

---

## 아키텍처

```
사용자 ─▶ mcs CLI ─┬─▶ Hermes (:8642) ── LLM, skill 실행
                   │       ├─ planner / extractor / instructor / objectives
                   │       └─ webhook-subscriptions (:8644)
                   │
                   └─▶ mcs daemon (:18342, MCP-HTTP)
                          ├─ memory / okr / inbox / entity / skill 16+ MCP 도구
                          ├─ Milvus + bge-m3 하이브리드 검색
                          └─ brain/ 파일 watcher
                                  │
                                  ▼
                            brain/  (마크다운 SSoT)
```

- **mcs 는 LLM을 호출하지 않는다.** 모든 모델 호출은 Hermes 단독 책임.
- **Brain 은 도구 중립.** 어떤 에디터로 편집해도 watcher 가 frontmatter 를 맞춰준다.
- **CLI 두 갈래.** mechanical 명령은 `mcs daemon` 으로 직행, agent 명령은 Hermes gateway 로 위임.

---

## 환경 설정

### 0. 사전조건

- macOS / Linux, **Python 3.13+**, [`uv`](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) — `bge-m3` 임베딩 + `qwen3.6:35b-a3b-mxfp8` fallback 모델 pull
- **Hermes 런타임** — 별도 설치 (LLM/스킬 실행 담당). mcs 만으로는 에이전트 기능 불가.

### 1. 클론 & 설치

```bash
git clone <this-repo> magic-conch-shell
cd magic-conch-shell
uv sync
```

### 2. `.env` 작성

```bash
cp .env.example .env
```

채울 항목:

| 키 | 용도 |
|---|---|
| `NOTION_TOKEN` | Notion integration secret |
| `NOTION_DAILY_TASKS_DB`, `NOTION_CALENDAR_DB` | DB UUID |
| `OLLAMA_BASE_URL` | 기본 `http://localhost:11434/v1` |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | `ollama` / `bge-m3` |

경로 오버라이드(`MCS_BRAIN_DIR`, `MCS_CACHE_DIR`)는 기본값이면 생략.

### 3. Hermes 연결

`~/.hermes/config.yaml` 에:

```yaml
skills:
  external_dirs:
    - ~/Documents/GitHub/magic-conch-shell/skills

mcp_servers:
  mcs:
    url: "http://127.0.0.1:18342/mcp/"

fallback_model:
  provider: custom
  base_url: "http://127.0.0.1:11434/v1"
  model: qwen3.6:35b-a3b-mxfp8
```

`~/.hermes/.env` 에:

```dotenv
API_SERVER_ENABLED=true
API_SERVER_KEY=<랜덤 토큰>
```

### 4. 기동

```bash
mcs daemon start --daemon    # :18342 (mcs MCP)
hermes gateway run           # :8642  (Hermes API)
# (선택) webhook-subscriptions :8644 — 데몬→Hermes 이벤트용
```

### 5. 점검

```bash
mcs doctor
mcs capture "hello shell"
```

<img src="docs/images/readme/doctor-pass.png" width="720" alt="mcs doctor — 환경 헬스체크 전부 통과">
<!-- TODO 스크린샷: mcs doctor 가 ✓ 로 통과한 화면 -->

---

## CLI 빠른 참조

자세한 옵션은 `mcs <cmd> --help`.

| 명령군 | 한 줄 요약 |
|---|---|
| `mcs daemon` | MCP 데몬 라이프사이클 (start/status/stop) |
| `mcs capture` | 자유 메모 + KR 진척 (`--kr`, `--increment`) |
| `mcs log` | 템플릿 기반 구조화 기록 |
| `mcs search` | 하이브리드 검색 (`-d`, `-e`, `--json`) |
| `mcs show` | slug/path 로 본문 + frontmatter |
| `mcs day` | 일일 저널 뷰 (FR-B3) |
| `mcs brief` | 아침 브리프 (FR-D1) |
| `mcs retro` | 저녁 회고 (FR-D3) |
| `mcs okr` | OKR 라이프사이클 (`new`, `update`, `sync`, `list`, `kr-*`, `close`) |
| `mcs inbox` | FR-G3 generic inbox (`list`, `approve`, `defer`, `reject`) |
| `mcs entity` | 엔티티 관리 (FR-C1/C3/C5) |
| `mcs skill` | 스킬 승격 드래프트 (FR-E5) |
| `mcs reindex` | 벡터 + 엔티티 풀 재빌드 (FR-I2) |
| `mcs doctor` | 환경 헬스체크 (FR-I1) |

공통 옵션:

- `--json` — 모든 조회 명령
- `--direct` — mcs 데몬 우회 (디버깅·오프라인)

---

## 디렉토리 구조

```
brain/             마크다운 SSoT
  signals/         자유 캡처
  domains/         career / ml / health-* / finance / relationships / general
  objectives/      분기별 OKR (2026-Q2 …)
  entities/        people / companies / jobs / drafts
  daily/           일일 저널
skills/            Hermes 가 읽는 스킬
  planner/         9개 — 대화형 워크플로 (okr-intake, capture-intake, daily-plan …)
  extractor/       3개 — 캡처 후 분석 (entity-extract, domain-classify, skill-name-suggest)
  instructor/      1개 — 코칭 (interview-prep)
  objectives/      KR-당 자동 생성
src/mcs/
  commands/        14개 CLI 명령
  adapters/        Notion, Hermes, Memory, OKR, Inbox, Entity, Skill, …
  engine/          memory + okr 코어
docs/              설계 / 요구사항 / FR 노트 / tech 비교
```

---

## Identity 파일

프로젝트 루트의 3개 파일이 Hermes Agent 시스템 프롬프트로 자동 주입된다.

| 파일 | 역할 |
|---|---|
| [`SOUL.md`](SOUL.md) | 인격·톤·금지사항·기본 행동 |
| [`AGENTS.md`](AGENTS.md) | 프로젝트 규약·스킬 라우팅·경계·도구 허용 |
| `USER.md` → `brain/USER.md` | 사용자 프로필 (학습 + 수동, symlink) |
