# FR-H2: 기존 시스템 읽기 (Notion + 캘린더)

**카테고리**: H. Integration
**우선순위**: 높음 (MVP 필수 — 외부 시그널 유일 소스)

---

## 1. Overview

**Notion DB 및 캘린더**에서 정보를 **읽기 전용** 참조. 아침 브리핑·세션 맥락 등에 활용.

MVP 외부 시그널 = 이것만. 이메일·웹은 v1.0.

---

## 2. 관련 컴포넌트

- **Tools**: `tools/notion.py` (read_db, read_calendar)
- **MCP**: `notion_read_db`, `notion_read_calendar`
- **Skills**: `morning-brief`이 주 소비자

---

## 3. 읽기 대상

| 대상 | Notion 내부 | 쿼리 |
|---|---|---|
| Daily Tasks (오늘) | DB3 | Date=today |
| Daily Tasks (어제 미완료) | DB3 | Date=yesterday AND Status≠Done |
| OKR·KR 현재값 | DB1, DB2 | Rollup |
| Job Pipeline | DB6 | status ∈ {interviewing, applied} |
| 캘린더 (오늘) | Notion Calendar | Date=today |
| 캘린더 (이번 주) | Notion Calendar | Date range |

---

## 4. 구현

```python
async def read_db(db_id: str, filter: dict | None = None, sort: list | None = None) -> list[dict]:
    client = _get_client()
    pages = []
    cursor = None
    while True:
        response = await client.databases.query(
            database_id=db_id,
            filter=filter,
            sorts=sort,
            start_cursor=cursor,
        )
        pages.extend(response["results"])
        if not response["has_more"]:
            break
        cursor = response["next_cursor"]
    return [_normalize_page(p) for p in pages]

def _normalize_page(page: dict) -> dict:
    """Convert Notion page to plain dict with flattened properties."""
    props = {}
    for name, value in page["properties"].items():
        props[name] = _flatten_property(value)
    return {
        "id": page["id"],
        "url": page["url"],
        "created_time": page["created_time"],
        "last_edited_time": page["last_edited_time"],
        **props,
    }
```

### 헬퍼: 오늘 태스크
```python
async def today_tasks(daily_tasks_db_id: str) -> list[dict]:
    today_iso = date.today().isoformat()
    return await read_db(
        db_id=daily_tasks_db_id,
        filter={"property": "Date", "date": {"equals": today_iso}},
        sort=[{"property": "우선순위", "direction": "ascending"}],
    )
```

### 캘린더
Notion Calendar도 DB로 취급 (calendar view가 있는 DB).
```python
async def calendar_events(cal_db_id: str, start: date, end: date) -> list[dict]:
    return await read_db(
        db_id=cal_db_id,
        filter={"and": [
            {"property": "Date", "date": {"on_or_after": start.isoformat()}},
            {"property": "Date", "date": {"on_or_before": end.isoformat()}},
        ]},
    )
```

---

## 5. 읽기 전용 원칙

- `update_page` 호출하지 않음
- 우리가 쓴 것(`Source=magic-conch`)만 쓸 수 있고, 나머지는 읽기만
- 읽기 후 캐싱 (짧은 TTL 1분) — 반복 호출 방지

---

## 6. 테스트 포인트

- [ ] Daily Tasks 오늘 조회 성공
- [ ] 어제 미완료 필터 정확
- [ ] 캘린더 이벤트 조회
- [ ] 대량 (100건+) 페이지네이션 정상
- [ ] 외부 장애 시 None 반환 + 로그
- [ ] 캐시 TTL 동작

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| rate limit (초당 3건) | 배치 + 캐시 |
| 스키마 변경 | normalize_page에서 유연하게 |
| Secret 노출 | 로그에서 token 마스킹 |

---

## 8. 관련 FR

- **FR-D1** 아침 브리핑 (주 소비)
- **FR-D4** 주간 리뷰
- **FR-H1** 쓰기 (같은 SDK)

---

## 9. 구현 단계

- **Week 3 Day 5**: read_db 기본
- **Week 3 Day 6**: calendar 통합
- **Week 3 Day 7**: 캐싱
