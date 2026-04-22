# FR-I3: 장애 대응 (로컬 큐 + 제한 기능 지속)

**카테고리**: I. Admin
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

외부 서비스 장애 시 **의존 작업은 로컬 큐**, **독립 작업(캡처·검색)은 계속 동작**. 사용자 흐름 중단 없음.

---

## 2. 관련 컴포넌트

- **State**: `.brain/pending-push.jsonl`
- **Tools**: `state` (큐 관리), `llm.call` (fallback chain)
- **Commands**: `mcs queue list`, `mcs queue retry`

---

## 3. 외부별 장애 대응

### Codex OAuth (외부 LLM)
```
호출 실패
   → Ollama 로컬 fallback
   → 사용자 응답 품질 약간 낮아지지만 계속
   → 주기적으로 Codex 재시도 (5분)
   → 복구되면 자동 복귀
```

### Notion API
```
create/update 실패
   → .brain/pending-push.jsonl append
   → autopilot 5분마다 재시도 (backoff)
   → 5회 실패 → failed 플래그 + 사용자 알림
   → 독립 작업(capture·search·local session)은 정상 동작
```

### iMessage (Hermes)
```
Hermes 또는 iMessage adapter 실패
   → 터미널·파일 출력 fallback
   → brain/daily/.../DD.md에 "iMessage 미발송" 메모
   → Hermes 복구 감지 시 미발송 알림 일괄 전송 옵션
```

### memsearch
```
인덱스 접근 실패
   → grep·file 기반 fallback 검색 (느림·품질 낮음)
   → 사용자에게 "검색 성능 저하 — mcs reindex 권장" 알림
```

### Ollama
```
로컬 LLM 다운
   → Codex OAuth로 (민감 아닌 작업만)
   → 민감 작업 대기 + 사용자 알림
   → Ollama 재시작 시도 (launchd)
```

---

## 4. 큐 포맷

`.brain/pending-push.jsonl`:
```jsonl
{"id": "uuid", "ts": "...", "op": "create", "db": "daily_tasks", "payload": {...}, "retries": 0, "last_error": null, "next_retry_at": "..."}
{"id": "uuid", "ts": "...", "op": "update", "db": "daily_tasks", "target_page_id": "...", "payload": {...}, "retries": 3, "last_error": "rate_limit", "next_retry_at": "..."}
```

---

## 5. Retry 정책

```python
BACKOFF = [5, 10, 30, 120, 600, 1800]  # seconds
MAX_RETRIES = 5

async def retry_push_queue():
    items = await state.read_jsonl(".brain/pending-push.jsonl")
    now = now_kst()
    for item in items:
        if item["retries"] >= MAX_RETRIES:
            item["status"] = "failed"
            continue
        if parse_iso(item["next_retry_at"]) > now:
            continue  # 아직 대기
        try:
            await _execute_push(item)
            item["status"] = "success"
        except Exception as e:
            item["retries"] += 1
            item["last_error"] = str(e)
            wait = BACKOFF[min(item["retries"], len(BACKOFF) - 1)]
            item["next_retry_at"] = (now + timedelta(seconds=wait)).isoformat()
    await state.write_jsonl(".brain/pending-push.jsonl", items)
```

---

## 6. CLI

```bash
# 큐 상태
mcs queue list
mcs queue list --failed

# 수동 재시도
mcs queue retry {id}
mcs queue retry --all

# 삭제 (실패 영구)
mcs queue delete {id}

# 큐 전체 정리 (주의)
mcs queue clear --confirm
```

---

## 7. 테스트 포인트

- [ ] Notion 다운 시 capture·search 정상
- [ ] Notion 복구 시 큐 자동 처리
- [ ] Codex 실패 시 Ollama fallback
- [ ] iMessage 실패 시 터미널 출력
- [ ] 5회 실패 → failed + 알림
- [ ] `mcs queue list`로 잔여·실패 확인
- [ ] 수동 재시도 성공

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 큐 파일 커짐 (장기 장애) | 오래된 성공 항목 aging out |
| 재시도 폭주 (대량 큐) | concurrency 제한 + 스로틀 |
| Fallback LLM 품질 문제 | 사용자에게 "저하 모드" 알림 |
| 사용자가 실패 무시 | 아침 브리핑에 실패 큐 요약 |

---

## 9. 관련 FR

- **FR-D5** push (주 실패 지점)
- **FR-H1~H3** 외부 연동
- **FR-I1** doctor (상태 표시)
- **NFR-04** 신뢰성

---

## 10. 구현 단계

- **Week 3 Day 4**: pending-push.jsonl 기본
- **Week 3 Day 5**: 재시도 autopilot 루프
- **Week 4 Day 2**: 각 외부별 fallback 로직
- **Week 4 Day 3**: `mcs queue` CLI
