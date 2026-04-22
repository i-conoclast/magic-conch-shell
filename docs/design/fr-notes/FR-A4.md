# FR-A4: 마크다운 파일 watcher 기반 자동 수집

**카테고리**: A. Capture
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

사용자가 **외부 편집기·노트 앱**에서 마크다운 파일을 지정 폴더에 저장하면, 시스템이 **자동 감지·수집**. FR-A1의 채널 3 구체화.

---

## 2. 관련 컴포넌트

- **Tools**: `file.watch`, `memory.capture`, `memory.ingest_file`
- **Skills**: 저장 후 `entity-extract` 비동기 발동
- **Hooks**: 없음 (MVP)
- **자체 데몬**: `src/mcs/watcher.py` (launchd or Hermes cron으로 실행)

---

## 3. 데이터 플로우

```
사용자: 외부 편집기에서 brain/incoming/new-idea.md 저장
   → watchdog (macOS FSEvents) 감지
   → mcs watcher 이벤트 핸들러
   → SHA256 해시 계산 → 이미 처리됐나 확인 (FR-A5)
   → frontmatter 파싱 시도
     - 있으면: 기존 메타 사용
     - 없으면: 기본값 생성 (type=note, domain=null)
   → 정본 위치로 이동/복사 (brain/signals 또는 brain/domains/X)
   → memsearch live sync 자동 재인덱싱
   → entity-extract skill 비동기 발동
```

---

## 4. 감시 대상 폴더

**기본**:
- `brain/incoming/` — 사용자가 드롭박스처럼 사용
- (선택) 사용자 지정 외부 폴더 (`config.yaml`에 추가)

**예외** (감시 안 함):
- `brain/signals/` — 시스템이 쓰는 영역
- `brain/domains/*/` — 이미 정본
- `brain/entities/` — 별도 관리
- 숨김 파일 (`.`), 백업 (`~`, `.bak`, `.swp`)
- 임시 파일 (`tmp_*`, `~$*`)

---

## 5. 수집 파일 예시

### 프론트매터 있는 경우
사용자가 쓴 파일:
```markdown
---
domain: ml
entities: [people/chip-huyen]
tags: [reading]
---

"Designing ML Systems" 5장 읽음. 데이터 드리프트 부분이 핵심.
```

→ 시스템이 보강:
```markdown
---
id: 2026-04-19-designing-ml-5ch
type: note
domain: ml
entities: [people/chip-huyen]
tags: [reading]
created_at: 2026-04-19T14:22:30+09:00   # 파일 생성 시각
source: file-watcher
original_path: brain/incoming/new-idea.md
---

"Designing ML Systems" 5장 읽음. 데이터 드리프트 부분이 핵심.
```

→ 저장: `brain/domains/ml/2026-04-19-designing-ml-5ch.md`

### 프론트매터 없는 경우
내용만:
```markdown
생각: agent의 자기 개선은 위험할 수도. 통제 필요.
```

→ 시스템이 기본값으로:
```markdown
---
id: 2026-04-19-142230
type: signal
domain: null
entities: []
created_at: 2026-04-19T14:22:30+09:00
source: file-watcher
---

생각: agent의 자기 개선은 위험할 수도. 통제 필요.
```

→ 저장: `brain/signals/2026-04-19-142230.md`

---

## 6. 의존성·전제

- `watchdog` (파이썬 패키지)
- macOS FSEvents 지원 (M4 Pro)
- `python-frontmatter`로 파싱
- `incoming/` 폴더 기본 생성 (설치 스크립트가 초기화)
- `.brain/state.json`에 처리된 파일 해시 기록

---

## 7. 구현 노트

### 7.1 Watcher 데몬
```python
# src/mcs/watcher.py
import asyncio
import hashlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
from tools import memory, file

WATCH_DIRS = [Path("brain/incoming")]
IGNORE_PREFIXES = {".", "~", "tmp_"}
IGNORE_SUFFIXES = {".bak", ".swp"}

class IngestHandler(FileSystemEventHandler):
    def on_created(self, event):
        self._process(event.src_path)

    def on_modified(self, event):
        self._process(event.src_path)

    def _process(self, path_str: str):
        path = Path(path_str)
        if not path.suffix == ".md":
            return
        if any(path.name.startswith(p) for p in IGNORE_PREFIXES):
            return
        if any(path.name.endswith(s) for s in IGNORE_SUFFIXES):
            return

        asyncio.create_task(ingest_file_safe(path))

async def ingest_file_safe(path: Path):
    try:
        await memory.ingest_file(path)
    except Exception as e:
        log.error(f"ingest failed: {path} - {e}")

def start():
    handler = IngestHandler()
    observer = Observer()
    for d in WATCH_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        observer.schedule(handler, str(d), recursive=True)
    observer.start()
    try:
        while True:
            asyncio.sleep(60)
    finally:
        observer.stop()
        observer.join()
```

### 7.2 Ingest 로직 (tools/memory.py)
```python
async def ingest_file(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    file_hash = hashlib.sha256(content.encode()).hexdigest()

    # 중복 감지 (FR-A5 연계)
    if await state.is_processed(file_hash):
        log.info(f"skip (already processed): {path}")
        return {"status": "skipped", "reason": "duplicate"}

    # 프론트매터 파싱
    post = frontmatter.loads(content)
    meta = post.metadata
    body = post.content

    # 기본값 채우기
    meta.setdefault("id", generate_slug(path, body))
    meta.setdefault("type", "note" if meta.get("domain") else "signal")
    meta.setdefault("domain", None)
    meta.setdefault("entities", [])
    meta.setdefault("created_at", now_kst().isoformat())
    meta["source"] = "file-watcher"
    meta["original_path"] = str(path)

    # 정본 저장
    target_folder = f"brain/domains/{meta['domain']}" if meta["domain"] else "brain/signals"
    target_path = Path(target_folder) / f"{meta['id']}.md"

    await file.write(target_path, frontmatter.dumps(frontmatter.Post(body, **meta)))

    # 원본 제거 (incoming에서 정본으로 이동 완료)
    path.unlink()

    # 상태 기록
    await state.mark_processed(file_hash, target_path)

    # 후속 처리
    asyncio.create_task(hermes.run_skill("entity-extract", context={"path": str(target_path)}))

    return {"status": "ingested", "path": str(target_path), "id": meta["id"]}
```

---

## 8. 테스트 포인트

- [ ] `brain/incoming/test.md` 생성 → 1분 이내 `brain/signals/*.md`로 이동
- [ ] 프론트매터 있는 파일 → 메타 정보 보존
- [ ] 프론트매터 없는 파일 → 기본값 채워짐
- [ ] 숨김 파일·백업 파일 무시
- [ ] 같은 파일 두 번 저장 → 두 번째 skip (해시 일치)
- [ ] 수정 이벤트 → 기존 정본 업데이트
- [ ] watcher 비정상 종료 후 재시작 가능 (state.json 복구)

---

## 9. 리스크·완화

| 리스크 | 완화 |
|---|---|
| FSEvents가 단기간에 여러 이벤트 발생 (저장 중) | 디바운스 (1초 지연) |
| 큰 파일 저장 시 파싱 오래 걸림 | 비동기 처리, 원본은 즉시 incoming에서 이동 |
| 프론트매터 문법 오류 | 실패 시 `brain/incoming/failed/`로 이동 + 로그 |
| 사용자가 수정 중인 파일을 이동 | incoming에서 **일정 시간 안정된 뒤** 이동 (5초 dwell) |
| watcher 프로세스 죽음 | launchd KeepAlive + `mcs doctor`로 감지 |

---

## 10. 관련 FR

- **FR-A1** 텍스트 캡처 (채널 3의 구체)
- **FR-A5** 중복 감지 (핵심 연계)
- **FR-C1** 엔티티 초안 (ingest 후 발동)
- **FR-I1** 상태 점검 (watcher 상태 포함)
- **FR-I3** 장애 대응 (watcher 죽음 감지)

---

## 11. 구현 단계

- **Week 1 Day 6**: watchdog 기본 handler + incoming 폴더
- **Week 1 Day 7**: frontmatter 파싱 + 기본값 채우기 + 정본 이동
- **Week 2 Day 1**: 중복 해시·state 관리
- **Week 4 Day 1**: launchd plist 또는 Hermes cron 등록
