# FR-I1: 상태 점검 (mcs doctor)

**카테고리**: I. Admin
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

`mcs doctor` — 시스템 전반 상태 한 번에 점검. 솔로 운영 필수.

---

## 2. 관련 컴포넌트

- **Commands**: `mcs doctor`
- **Tools**: 각 레이어 점검 함수

---

## 3. 점검 항목 (완전 목록)

### Identity
- [ ] SOUL.md 존재·파싱
- [ ] AGENTS.md 존재·파싱
- [ ] USER.md symlink 유효 (brain/USER.md 가리킴)

### Configuration
- [ ] config.yaml / .env 존재
- [ ] NOTION_TOKEN / OAuth tokens 유효

### Data
- [ ] brain/ 디렉토리 존재·권한
- [ ] brain/ 필수 하위 폴더 (daily, domains, entities, signals, plans, session-state)
- [ ] .brain/ 캐시 디렉토리 쓰기 가능

### Indexes
- [ ] memsearch DB 접근 가능
- [ ] 마지막 인덱싱 시각 (너무 오래됐나)

### Background processes
- [ ] watcher 프로세스 살아있음 (FR-A4)
- [ ] Hermes 프로세스 살아있음
- [ ] Ollama 서버 응답 (:11434)
- [ ] MCP 서버 stdio로 Hermes에 연결됨

### External services
- [ ] Notion API 연결 (read DB list)
- [ ] Codex OAuth 토큰 유효
- [ ] iMessage adapter (Hermes 설정)

### Queues
- [ ] pending-push.jsonl 잔여 수
- [ ] approval-inbox.jsonl 잔여 수 (수동 처리 필요 임계)
- [ ] streak-state.json 파싱 가능

### Recent activity
- [ ] 마지막 capture 시각
- [ ] 마지막 morning-brief 실행
- [ ] 마지막 evening-retro 실행
- [ ] 최근 오류 로그 (.brain/logs/)

---

## 4. 출력 예시

```
$ mcs doctor
╭─ Identity ──────────────────────────────────────╮
│ ✅ SOUL.md                                      │
│ ✅ AGENTS.md                                    │
│ ✅ USER.md (symlink → brain/USER.md)            │
╰─────────────────────────────────────────────────╯
╭─ Data ──────────────────────────────────────────╮
│ ✅ brain/ (247 MB, 1,432 files)                 │
│ ✅ .brain/ cache                                │
│ ✅ memsearch DB (last indexed: 12m ago)         │
╰─────────────────────────────────────────────────╯
╭─ Processes ─────────────────────────────────────╮
│ ✅ File watcher (pid 12345, uptime 3d 2h)       │
│ ✅ Hermes Agent (gateway running)               │
│ ✅ Ollama (:11434, qwen3:27b loaded)            │
│ ✅ MCP server (connected to Hermes)             │
╰─────────────────────────────────────────────────╯
╭─ External ──────────────────────────────────────╮
│ ✅ Notion API (3 DBs accessible)                │
│ ✅ Codex OAuth (token valid until 2026-05-19)   │
│ ✅ iMessage adapter                             │
╰─────────────────────────────────────────────────╯
╭─ Queues ────────────────────────────────────────╮
│ ⚠️  Pending Notion push: 2                      │
│ ⚠️  Approval inbox: 5 items (3 days old)        │
╰─────────────────────────────────────────────────╯
╭─ Activity ──────────────────────────────────────╮
│ Last capture: 14m ago                           │
│ Last morning-brief: today 07:15 ✅              │
│ Last evening-retro: yesterday 22:35 ✅          │
│ Recent errors: 0                                │
╰─────────────────────────────────────────────────╯

Summary: 2 warnings, 0 errors.

Suggestions:
  - Process approval inbox (/retro)
  - Review pending push queue (mcs queue list)
```

---

## 5. 구현 노트

```python
# commands/doctor.py
@app.command()
def doctor(
    verbose: bool = typer.Option(False, "-v"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    checks = [
        ("Identity", check_identity),
        ("Data", check_data),
        ("Indexes", check_indexes),
        ("Processes", check_processes),
        ("External", check_external),
        ("Queues", check_queues),
        ("Activity", check_activity),
    ]
    results = {}
    for name, fn in checks:
        results[name] = asyncio.run(fn())

    if as_json:
        typer.echo(json.dumps(results, indent=2))
    else:
        render_rich(results, verbose=verbose)
    return results
```

각 체크 함수는 `[{label, status, message}]` 반환.

---

## 6. 테스트 포인트

- [ ] 모든 섹션이 정상 상태에서 ✅ 표시
- [ ] 각 컴포넌트 다운 상태 모의 → 해당 항목 ❌
- [ ] 수 초 이내 완료
- [ ] `--json` 옵션 유효
- [ ] 오류 항목에 복구 가이드 메시지

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 체크 중 일부 실패로 전체 중단 | 각 체크 try/except, 부분 결과 반환 |
| 외부 서비스 호출로 doctor 오래 걸림 | 병렬 실행 + 타임아웃 |
| 민감 정보 로그 노출 | 토큰 마스킹 |

---

## 8. 관련 FR

- **FR-I2** 인덱스 재빌드 (doctor에서 힌트)
- **FR-I3** 장애 대응 (doctor 경고 → 복구 명령)
- 전반 모든 FR (상태 포함)

---

## 9. 구현 단계

- **Week 4 Day 3**: 각 체크 함수 + 단순 출력
- **Week 4 Day 4**: Rich 포맷팅
- **Week 4 Day 5~7**: 실사용 개선 (자주 보는 항목 우선)
