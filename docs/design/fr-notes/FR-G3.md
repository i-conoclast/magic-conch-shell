# FR-G3: 제안 인박스 (저녁 회고 일괄)

**카테고리**: G. Evolution
**우선순위**: 높음 (MVP 필수 — Step 2 침입성 원칙)

---

## 1. Overview

시스템이 하루 동안 만든 **제안·승인 대기 항목**을 **낮에는 보내지 않고** 저녁 회고 시간에 일괄 제시.

**잔소리 금지 원칙**의 구체 구현.

---

## 2. 관련 컴포넌트

- **State**: `.brain/approval-inbox.jsonl`
- **Tools**: `state.add_approval`, `state.get_approval_inbox`
- **Skills**: `evening-retro`가 Phase 2에서 처리 (FR-D3)

---

## 3. 인박스 항목 타입

```jsonl
{"ts": "...", "type": "entity-draft", "path": "...", "kind": "people", "name": "Jane Smith", "detected_at": "..."}
{"ts": "...", "type": "skill-promotion", "pattern": {...}, "detected_count": 4}
{"ts": "...", "type": "entity-merge-suggestion", "candidates": ["jane-smith", "j-smith"]}
{"ts": "...", "type": "proactive-suggestion", "content": "Jane 마지막 접촉 9일 전 — 내일 follow-up?"}
{"ts": "...", "type": "context-link", "content": "새 Anthropic 메일 감지. jobs/anthropic-mle와 연결?"}
```

---

## 4. 실시간 쌓임, 즉시 알림 X

```python
async def add_approval(item: dict) -> None:
    item["ts"] = now_kst().isoformat()
    item.setdefault("status", "pending")
    await state.append_jsonl(".brain/approval-inbox.jsonl", item)
    # **알림 없음** — 저녁 회고까지 대기
```

---

## 5. 저녁 회고 통합

FR-D3 Phase 2에서 get_approval_inbox() 호출:
```python
async def get_approval_inbox(include_deferred: bool = True) -> list[dict]:
    items = await state.read_jsonl(".brain/approval-inbox.jsonl")
    pending = [i for i in items if i["status"] == "pending"]
    if include_deferred:
        pending += [i for i in items if i["status"] == "deferred" and i.get("defer_until_today")]
    return pending
```

사용자 처리 후:
```python
async def mark_approval(item_id: str, decision: str) -> None:
    """decision: approve | reject | defer"""
    ...
```

---

## 6. 아침 브리핑에 "대기 N건" 상기

FR-D1 아침 브리핑이 인박스 대기 수 조회:
```
## 대기 중 승인 5건
(저녁 회고에서 처리)
```

임계값 초과(예: 10건) 시 더 강한 알림:
```
⚠️ 승인 대기 12건 — 저녁 회고에서 꼭 처리해주세요
```

---

## 7. 테스트 포인트

- [ ] 낮 동안 여러 항목 발생 → 사용자에게 알림 0건 (침입 없음)
- [ ] 저녁 회고에서 모든 pending 항목 제시
- [ ] 승인·거절·미루기 결과 반영
- [ ] 미루기한 항목 다음 회고에 재등장
- [ ] 임계 초과 시 아침 브리핑에 상기
- [ ] 인박스 파일 손상 시 복구 또는 재구축

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 너무 많이 쌓여 처리 포기 | 임계 임시 중단: 신규 제안 스킵 (기존 처리 우선 안내) |
| 잘못 승인·거절 후 되돌리기 | decision 로그 + undo 지원 (선택) |
| 인박스 파일 경합 (동시 쓰기) | append-only JSONL + 파일 락 |
| 사용자가 일주일 건너뜀 | 계속 누적. 아침에 안내 강도 증가. |

---

## 9. 관련 FR

- **FR-D3** 저녁 회고 (주요 처리 지점)
- **FR-C2** 엔티티 승인
- **FR-E5** 스킬 승격 승인
- **FR-G5** 논리 비약 챌린지 (실시간 VS 인박스 - 일부 실시간 허용)

---

## 10. 구현 단계

- **Week 2 Day 7**: approval-inbox.jsonl R/W 함수
- **Week 3 Day 1**: 각 feature에 add_approval 호출 주입
- **Week 3 Day 2**: evening-retro Phase 2 통합
- **Week 4 Day 2**: 아침 브리핑 대기 수 표시
