# FR-A1: 자유 메모 한 줄 캡처

**카테고리**: A. Capture
**우선순위**: 높음 (MVP 필수)
**출처**: [requirements/03-functional/A-capture-fr.md](../../requirements/03-functional/A-capture-fr.md)

---

## 1. Overview

사용자가 생각·아이디어·후기·관찰 한 줄을 **3개 채널** 중 어디서든 즉시 기록. 입력 직후 영속 저장 + 검색 가능.

**입력 채널**:
- 터미널 (CLI): `mcs capture "..."`
- 채팅 앱 (iMessage): 자연어 메시지
- 마크다운 파일 직접 타이핑: 감시 폴더에 `.md` 저장 (→ FR-A4로 이관)

FR-A4와 일부 겹치지만, 이 FR은 **명시적 한 줄 캡처** 경로에 집중. FR-A4는 **파일 watcher로 자동 수집**에 집중.

---

## 2. 관련 컴포넌트

### Skills
- 직접 쓰이는 skill 없음 (캡처는 도구 호출로 충분)
- `entity-extract` skill이 저장 후 **비동기 발동** (본문에서 엔티티 감지 → FR-G2)

### Agents
- 없음 (범용 에이전트가 처리)

### Commands
- `commands/capture.md` — `/capture` 슬래시 + `mcs capture` CLI

### Tools
- `memory` (주) — `memory_capture()`
- `file` — frontmatter 작성·저장

### Hooks
- `pre-external-write` (옵션) — 로깅용

### MCP Server
- `memory_capture` tool 노출

---

## 3. 데이터 플로우

```
Channel 1: Terminal
  사용자: $ mcs capture "LoRA 구현 복습 중"
         → Typer CLI (src/mcs/commands/capture.py)
         → tools.memory.capture(text=..., source="typed")
         → 저장

Channel 2: iMessage
  사용자: (iMessage) "LoRA 구현 복습 중"
         → Hermes iMessage adapter
         → Hermes가 "일반 메모로 보임" 자동 판단
         → MCP tool: mcs.memory_capture(text=..., source="chat")
         → 저장

Channel 3: 파일 타이핑 (→ FR-A4 참조)
  사용자: brain/signals/ 또는 감시 폴더에 .md 저장
         → watchdog 감지
         → tools.memory.capture(text=..., source="file-watcher")
         → 저장 (또는 이미 존재 시 업데이트)

저장 흐름 공통:
  capture() 내부:
    1. slug 생성 (YYYY-MM-DD-HHmmss 또는 kebab-title)
    2. frontmatter 조립 (id, type, domain, entities, source, created_at)
    3. brain/{signals 또는 domains/X}/... .md 작성
    4. memsearch live sync가 감지 → .brain/memsearch-db 재인덱싱
    5. 저장 결과 (path, id) 반환

후속 (비동기):
    6. entity-extract skill 호출 → 엔티티 초안 생성 (있으면)
    7. 대응 skill이 back-link 갱신 (FR-C3)
```

---

## 4. 입력 포맷

### 최소 입력
```
text: str  (필수)
```

### 옵션 (지정 가능)
```
domain: str | None          # 7 도메인 중 하나 또는 미지정
entities: list[str] | None  # 기존 엔티티 slug 목록
```

**도메인 미지정 시**: `brain/signals/`에 저장 (미분류).
**도메인 지정 시**: `brain/domains/{domain}/`에 저장.

---

## 5. 저장되는 파일 예시

### 도메인 미지정 (signals)

파일: `brain/signals/2026-04-19-142230.md`
```markdown
---
id: 2026-04-19-142230
type: signal
domain: null
entities: []
created_at: 2026-04-19T14:22:30+09:00
source: typed
---

LoRA 구현 복습 중
```

### 도메인 지정

파일: `brain/domains/ml/2026-04-19-142230.md`
```markdown
---
id: 2026-04-19-142230
type: note
domain: ml
entities: []
created_at: 2026-04-19T14:22:30+09:00
source: chat
---

LoRA 구현 복습 중
```

---

## 6. 의존성·전제

- `brain/signals/`, `brain/domains/{7개}/` 디렉토리 존재
- memsearch live sync 실행 중 (autopilot)
- iMessage 경로는 Hermes 정상 동작 + Mac mini iCloud 로그인
- MCP 서버 (`mcp/mcs-server.py`) 가동 → Hermes가 호출 가능

---

## 7. 구현 노트

### 7.1 CLI 구현 (src/mcs/commands/capture.py)

```python
import typer
from tools import memory

app = typer.Typer()

@app.command()
def capture(
    text: str = typer.Argument(..., help="Memo text"),
    domain: str | None = typer.Option(None, "--domain", "-d"),
    entity: list[str] | None = typer.Option(None, "--entity", "-e"),
    silent: bool = typer.Option(False, "--silent", "-s"),
) -> None:
    """Capture a one-line memo immediately."""
    result = asyncio.run(memory.capture(
        text=text,
        domain=domain,
        entities=entity or [],
        source="typed",
    ))
    if not silent:
        typer.echo(f"✓ Saved: {result['path']}")
```

### 7.2 MCP tool 노출 (mcp/mcs-server.py)

```python
@mcp.tool()
async def memory_capture(
    text: str,
    domain: str | None = None,
    entities: list[str] | None = None,
    source: str = "hermes",
) -> dict:
    """Capture a one-line memo. Returns {path, id}."""
    return await memory.capture(text=text, domain=domain, entities=entities, source=source)
```

### 7.3 core 로직 (tools/memory.py)

```python
async def capture(
    text: str,
    domain: str | None = None,
    entities: list[str] | None = None,
    source: str = "unknown",
) -> dict:
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    slug = now.strftime("%Y-%m-%d-%H%M%S")

    frontmatter = {
        "id": slug,
        "type": "note" if domain else "signal",
        "domain": domain,
        "entities": entities or [],
        "created_at": now.isoformat(),
        "source": source,
    }

    folder = f"brain/domains/{domain}" if domain else "brain/signals"
    path = f"{folder}/{slug}.md"

    body = f"---\n{yaml.dump(frontmatter)}---\n\n{text}\n"
    await file.write(path, body)

    # 비동기 후속 처리 (대기 X)
    asyncio.create_task(_post_capture(path))

    return {"path": path, "id": slug}

async def _post_capture(path: str):
    """Trigger entity-extract skill."""
    await hermes.run_skill("entity-extract", context={"path": path})
```

### 7.4 성능 목표

- CLI 입력 → 확인 출력: **2초 이내** (NFR-02)
- iMessage → 응답: 수 초 (Hermes 중재 포함)
- 파일 watcher → 감지: 1분 이내 (FR-A4 세부)

---

## 8. 테스트 포인트

### 단위 테스트 (pytest)
- [ ] `capture(text="test")` → `brain/signals/*.md` 생성 확인
- [ ] `capture(text="test", domain="ml")` → `brain/domains/ml/*.md` 생성 확인
- [ ] frontmatter 파싱 성공 (pyyaml)
- [ ] slug 형식 `YYYY-MM-DD-HHmmss` 준수
- [ ] 한국어·영어 혼용 텍스트 정상 저장
- [ ] 타임존 KST 유지

### 통합 테스트
- [ ] CLI `mcs capture "..."` → 2초 이내 저장 확인
- [ ] iMessage 한 줄 메시지 → Hermes가 MCP tool 호출 → 저장 확인
- [ ] 저장 직후 `mcs search`로 해당 메모 검색 성공
- [ ] 네트워크 오프라인 상태에서도 저장 성공 (로컬 우선)

### 실사용 테스트
- [ ] 하루 중 3 채널 모두 사용 — 모든 채널에서 일관된 저장 위치·포맷
- [ ] 도메인 미지정 메모가 저녁 회고에 "분류 안 된 메모"로 제시되는지 (→ FR-D3 연계)

---

## 9. 리스크·완화

| 리스크 | 완화 |
|---|---|
| **memsearch live sync 지연** — 저장 후 검색이 바로 안 됨 | MVP 허용 (분 단위). 재인덱싱 주기 설정. |
| **iMessage가 메모인지 질문인지 판단 오류** — Hermes가 질의로 해석 | `conch-answer` skill이 "캡처인지 질의인지" 초기 분류. 애매하면 사용자 확인. |
| **파일 watcher와 수동 입력 충돌** — 동시 저장 시 slug 충돌 | `YYYY-MM-DD-HHmmss`에 밀리초 추가 또는 suffix. FR-A5 중복 감지와 연계. |
| **한글 slug vs 영어 slug 혼재** | 자동 생성은 항상 타임스탬프 기반(영어). 타이핑 slug만 한글 허용. |
| **프라이버시 우려: 민감 메모 실수로 외부 LLM 전송** | 캡처 자체는 로컬만. entity-extract 호출 시 sensitive flag. |
| **대용량 입력** (한 줄이라 했지만 긴 문단 입력 시) | 1KB 상한 체크 후 경고. 초과 시 구조화 기록(FR-A2) 권유. |

---

## 10. 관련 FR

- **FR-A2** 구조화 기록 캡처 (템플릿 기반)
- **FR-A3** 도메인·엔티티 선택 캡처 (옵션 활용)
- **FR-A4** 파일 watcher 자동 수집 (Channel 3 구체)
- **FR-A5** 중복 감지
- **FR-B1** 자유 질의 검색 (캡처된 것을 찾는 반대 경로)
- **FR-C1** 자동 엔티티 초안 (캡처 후 비동기 발동)
- **FR-G2** 자동 엔티티 태깅 (캡처 후 비동기 발동)

---

## 11. 구현 단계

**Week 1 Day 2**: CLI 캡처 (`mcs capture`) 최소 동작.
**Week 1 Day 3**: frontmatter 조립 + 파일 저장 + domain 지원.
**Week 2 Day 2**: MCP tool 노출, Hermes에서 호출 성공.
**Week 2 Day 3**: iMessage 경로 통합 (conch-answer가 캡처로 라우팅).
**Week 3 Day 2**: entity-extract 후속 호출 연결.
