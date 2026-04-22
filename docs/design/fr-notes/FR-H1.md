# FR-H1: 외부 태스크 시스템 쓰기 (Notion Daily Tasks)

**카테고리**: H. Integration
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

확정 플랜을 Notion `Daily Tasks` DB에 자동 생성. plan-tracker와 스키마 공유.

---

## 2. 관련 컴포넌트

- **Tools**: `tools/notion.py` (create_page, update_page)
- **MCP**: `notion_create_page`, `notion_update_page`
- **Skills**: `plan-confirm`·`morning-brief`이 호출
- **State**: `.brain/pending-push.jsonl`

---

## 3. Notion 계약 (plan-tracker 공유)

[requirements/03-functional/H-integration-criteria.md](../../requirements/03-functional/H-integration-criteria.md) 기준.

### 쓰기 필드 (우리가 채움)
| Notion 필드 | 값 |
|---|---|
| Title | 플랜 제목 |
| Date | 계획 날짜 |
| 영역 (Domain) | career / health-physical / ... |
| 세부활동 | 상세 설명 |
| 우선순위 | high / medium / low |
| KR | Relation (선택) |
| 계획상태 | **"Planned" 고정** (다른 상태 X) |
| Source | **"magic-conch" 고정** |
| Brain Ref | `brain/plans/{slug}.md` 경로 |
| Confirmed At | ISO datetime |

### 쓰기 금지
- 완료 체크·실제값 — plan-tracker 영역
- 이미 생성된 페이지를 `Source=magic-conch` 외 상태로 변경

---

## 4. 구현 노트

```python
# tools/notion.py
from notion_client import AsyncClient

_client: AsyncClient | None = None

def _get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = AsyncClient(auth=os.environ["NOTION_TOKEN"])
    return _client

async def create_page(db_id: str, properties: dict) -> str:
    """Create a page in a database. Returns page_id."""
    client = _get_client()
    page = await client.pages.create(
        parent={"database_id": db_id},
        properties=properties,
    )
    return page["id"]

async def update_page(page_id: str, properties: dict) -> None:
    client = _get_client()
    await client.pages.update(page_id=page_id, properties=properties)
```

### Property 조립 헬퍼
```python
def to_daily_task_properties(plan: PlanItem, brain_ref: str) -> dict:
    return {
        "Title": {"title": [{"text": {"content": plan.title}}]},
        "Date": {"date": {"start": plan.date.isoformat()}},
        "영역": {"select": {"name": plan.domain}},
        "세부활동": {"rich_text": [{"text": {"content": plan.body[:2000]}}]},
        "우선순위": {"select": {"name": plan.priority}},
        "계획상태": {"select": {"name": "Planned"}},
        "Source": {"select": {"name": "magic-conch"}},
        "Brain Ref": {"url": f"file://{brain_ref}"},
        "Confirmed At": {"date": {"start": now_kst().isoformat()}},
        **({"KR": {"relation": [{"id": plan.kr_page_id}]}} if plan.kr_page_id else {}),
    }
```

---

## 5. 재시도·큐

FR-D5에서 상세. 핵심:
- 실패 → `.brain/pending-push.jsonl` append
- autopilot 5분마다 재시도 (exponential backoff)
- 5회 실패 시 failed, 사용자 알림

---

## 6. 테스트 포인트

- [ ] 단일 페이지 생성 성공
- [ ] 모든 필수 필드 반영
- [ ] rate limit 히트 시 backoff 대기
- [ ] 실패 → 큐 + 재시도로 복구
- [ ] 동일 slug 중복 push 방지
- [ ] Source="magic-conch" 외 레코드 수정 안 됨
- [ ] 계획상태 "Planned" 외로 쓰기 안 됨

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| Notion API 스키마 변경 | plan-tracker contract 버전 관리 |
| Token 만료·실패 | doctor에서 연결 체크 |
| 대량 push 시 rate limit | 배치 지연 (초당 3건 이하) |
| 네트워크 다운 | 로컬 큐 |

---

## 8. 관련 FR

- **FR-D5** 확정 플랜 반영 (주 호출)
- **FR-I3** 장애·큐
- **FR-H2** 읽기 (같은 SDK)

---

## 9. 구현 단계

- **Week 3 Day 3**: notion_client 초기화 + create_page
- **Week 3 Day 4**: property 조립 헬퍼
- **Week 3 Day 5**: MCP tool 노출
- **Week 3 Day 6**: 큐·재시도
