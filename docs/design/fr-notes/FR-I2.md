# FR-I2: 인덱스 재빌드

**카테고리**: I. Admin
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

`mcs reindex` — 검색 인덱스·back-link·state를 **brain/ 원본에서 재빌드**. 캐시 꼬임·불일치 복구.

---

## 2. 관련 컴포넌트

- **Commands**: `mcs reindex [--what]`
- **Tools**: `memsearch` 재인덱싱, `memory.rebuild_backlinks`

---

## 3. 재빌드 옵션

```bash
mcs reindex                  # 전체
mcs reindex --memsearch      # memsearch만
mcs reindex --backlinks      # entity back-links만
mcs reindex --state          # state.json·processed-hashes
mcs reindex --dry-run        # 체크만
```

---

## 4. 흐름

```
mcs reindex
   → 1. brain/ 전체 스캔
   → 2. memsearch DB 비우기 + 재인덱싱
      (모든 .md 파일 다시 임베딩)
   → 3. entity back-links 재스캔 (FR-C3)
   → 4. state.json 재구축
      (processed-hashes from brain/ scan)
   → 5. 요약 출력
```

---

## 5. 예시

```
$ mcs reindex
Scanning brain/... 1,432 files
Clearing memsearch DB... done
Reindexing memsearch...
  [████████████████████░░░░] 70% (1,002/1,432)
...
Reindexing complete.
Rebuilding back-links...
  247 entities processed
  3,847 back-links regenerated
State.json rebuilt.

Summary:
  - memsearch: 1,432 files indexed (2.3 min)
  - back-links: 3,847 links in 247 entities
  - state: 1,432 hashes tracked
```

---

## 6. 구현 노트

```python
@app.command()
def reindex(
    what: list[str] = typer.Option(["all"]),
    dry_run: bool = typer.Option(False),
) -> None:
    targets = set(what) if "all" not in what else {"memsearch", "backlinks", "state"}

    if dry_run:
        typer.echo(f"Would rebuild: {targets}")
        return

    if "memsearch" in targets:
        asyncio.run(_rebuild_memsearch())
    if "backlinks" in targets:
        asyncio.run(memory.rebuild_backlinks())
    if "state" in targets:
        asyncio.run(_rebuild_state())

async def _rebuild_memsearch():
    ms = _get_memsearch()
    ms.clear()
    for path in await file.list_all("brain/", pattern="*.md"):
        if _should_skip(path):
            continue
        await ms.index_file(path)

async def _rebuild_state():
    state = {"processed_hashes": {}}
    for path in await file.list_all("brain/"):
        content = await file.read(path)
        h = hashlib.sha256(content.encode()).hexdigest()
        state["processed_hashes"][h] = str(path)
    await state.write_full(state)
```

---

## 7. 테스트 포인트

- [ ] `mcs reindex` → memsearch·back-links·state 모두 재빌드
- [ ] `--dry-run` → 변경 없음, 계획만 출력
- [ ] 재빌드 중 검색 시도 → 임시 경고 또는 기존 인덱스 유지
- [ ] 재빌드 후 검색 품질 유지
- [ ] 재빌드 실패 시 기존 인덱스 보존 (트랜잭션)

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 재빌드 중 사용자가 검색 시도 | 기존 인덱스 유지, 완료 후 atomic swap |
| 도중 실패 → 불완전 인덱스 | 임시 DB에 빌드 후 성공 시 swap |
| 오래 걸림 (1000+ 파일) | 진행률 표시 + 백그라운드 옵션 |

---

## 9. 관련 FR

- **FR-A5** 중복 감지 (state 재구축)
- **FR-B1** 검색 (memsearch)
- **FR-C3** back-link
- **FR-I1** doctor (재빌드 권장 시점)

---

## 10. 구현 단계

- **Week 2 Day 1**: memsearch 재인덱싱 함수
- **Week 4 Day 2**: back-links 재스캔
- **Week 4 Day 3**: state 재구축
- **Week 4 Day 4**: `mcs reindex` CLI
