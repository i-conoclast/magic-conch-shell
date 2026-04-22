# FR-D1: 아침 브리핑 생성

**카테고리**: D. Planning
**우선순위**: 최상위 (MVP 최소 승리 조건 — Step 7)

---

## 1. Overview

매일 07:00 KST **자동 실행**. 오늘 태스크·어제 놓친 것·최근 변화를 한 번에 요약해 iMessage 전송.

> MVP 성공 신호: 사용자가 "이 자식 진짜 내를 알아"라고 느끼는 브리핑.

---

## 2. 관련 컴포넌트

- **Skills**: `morning-brief` (주)
- **Agents**: `planner` (선택, 톤 강화시)
- **Commands**: `/brief`, `mcs brief`
- **Tools**: `memory`, `notion`, `llm`, `hermes`, `file`
- **스케줄러**: Hermes 내장 cron

---

## 3. 데이터 플로우

```
Hermes cron 07:00 → /brief 트리거
   → morning-brief skill 로드
   → Step 1: context 수집
     - memory_daily("어제")                     → 어제 일지
     - memory_search(미완료 태스크)
     - notion_read_db(today's tasks)
     - notion_read_calendar(today)
     - memory_search(최근 7일 엔티티 활동)
     - brain/USER.md 읽기 (선호)
     - **도메인별 OKR·KR 현황** (7 도메인 각각):
       - **plan-tracker MCP 호출**: `okr_snapshot_current()` (전체)
       - 각 도메인별: 활성 Objective · KR · 현재값 · 달성률 · 이번 주 목표
       - plan-tracker가 `kr_snapshots` PG에서 최신 집계 반환
       - (캐싱: 1시간 TTL — 아침에 매번 재호출 안 함)
       - plan-tracker 다운 시: OKR 섹션 **graceful 생략**
   → Step 2: llm.call(model=codex-oauth)
     - 시스템 프롬프트: SOUL.md + AGENTS.md + morning-brief 지침
     - 사용자 프롬프트: 수집된 context (OKR·KR 포함)
     - 요청: 브리핑 텍스트 (컨설팅 톤, 선택지 + 근거)
     - **우선순위 판단 기준**: 각 도메인 OKR·KR과의 정렬성
   → Step 3: 저장·전송
     - file.write(brain/daily/YYYY/MM/DD.md) — 🌅 섹션에 append
     - hermes.send_imessage(brief_text)
   → Step 4: plan-confirm 대기 상태 진입 (사용자 응답시 FR-D2)
```

---

## 4. 브리핑 구성 요소 (출력)

```markdown
🌅 Morning Brief — 2026-04-19 (금)

**오늘 우선순위 3** (OKR 정렬)
1. Anthropic Jane follow-up 메일 (4/25 마감)
   → O1 커리어 · KR 1.4 지원 40건 (현재 12건, 30%)
2. ML 공부 2시간 (LoRA 논문 섹션 4)
   → O6 ML 공부 · KR 6.2 논문 정리 월 4편 (이번달 2편, 50%)
3. 주간 리뷰 준비 (일요일 20:00)

**어제 놓친 것 (1)**
- 블로그 초안 1시간 → 오늘 오전으로 이월?
  → O1 KR 1.2 영문 블로그 12편 (현재 3편, 25%) 진행 지연

**최근 변화 (2)**
- Anthropic Jane, 2차 일정 조율 중 (4/17 확인)
- 이번 주 운동 3회 완료 (+1 vs 지난주)
  → O2 건강(신체) KR 2.1 주 3회 이상 ✅ 달성

**도메인 OKR 주의**
- O5 재무 · KR 5.3 비상금 적립: 이번달 60% (7월 목표)
- O3 멘탈 · KR 3.1 번아웃 신호 제로: 이번주 2건 감지 (수면 4.5h)

**오늘 캘린더 (2)**
- 14:00 팀 스탠드업 (30분)
- 16:30 Claude 대화 (1h)

**질문**: 오늘 가장 미룰까 고민 중인 건?
```

**톤 규칙** (SOUL.md 준수):
- 데이터 근거 명시 (**OKR·KR 수치 포함**)
- 질문 한 줄로 대화 유도
- 아첨 금지

**우선순위 로직**: 각 후보 태스크를 도메인 OKR·KR과 매칭. **진도 뒤처진 KR**을 도와주는 태스크를 우선 배치.

---

## 5. SKILL.md

`skills/morning-brief/SKILL.md`:
```markdown
---
name: morning-brief
description: Generate daily morning briefing at 07:00 KST with today's tasks, yesterday misses, external signals, and a conversation-opening question
trigger:
  - cron: "0 7 * * *"
  - command: /brief
tools: [memory, notion, llm, file, hermes]
model: codex-oauth
sensitive: false
timeout: 60
---

# Morning Brief

## Purpose
오늘의 시작을 위한 대화형 브리핑. 사용자가 읽고 응답해서 플랜 확정으로 이어진다.

## Steps
1. memory.daily("yesterday") 로 어제 일지 읽기
2. memory.search(entities=[...], since="지난 7일") 로 최근 변화
3. notion.read_db("Daily Tasks", filter={date: today}) 로 오늘 예정
4. notion.read_calendar(today) 로 캘린더
5. llm.call(model="codex-oauth", prompt=brief_prompt(context))
6. file.write(brain/daily/YYYY/MM/DD.md) — 🌅 Morning Brief 섹션에 기록
7. hermes.send_imessage(user, brief_text)

## Prompt template
(see prompt.md)

## References
- [prompt.md](prompt.md)
- [example-output.md](example-output.md)
```

---

## 6. 프롬프트 예시

```
You are the magic conch shell generating a morning briefing.
Follow SOUL.md personality strictly.

## Context

### Yesterday's log
{yesterday_daily}

### Unfinished tasks
{unfinished_tasks}

### Today's scheduled tasks (Notion)
{today_tasks}

### Today's calendar
{today_calendar}

### Recent entity activity (last 7 days)
{entity_activity}

### User preferences (USER.md snippets)
{user_preferences}

## Task

Generate a morning briefing with these sections:
1. Today's priorities (top 3, with reasoning)
2. Yesterday's misses (1-3 items)
3. Recent changes (2-3 items, external signals)
4. Today's calendar (condensed)
5. One opening question

Rules:
- Use consulting tone (options + reasoning, not orders)
- Stay under 300 words
- Korean natural, English OK where appropriate
- No flattery
```

---

## 7. 구현 노트

### skills/morning-brief/SKILL.md에서 실행되는 로직
Hermes가 SKILL.md의 steps를 해석해서 MCP tools 호출. 직접 Python 구현이 아님.

### 지원 코드 (tools/okr.py + tools/memory.py)

**`tools/okr.py`** — plan-tracker MCP client wrapper (thin):

```python
# tools/okr.py
from fastmcp.client import Client as MCPClient
from datetime import date, timedelta
import os

_client: MCPClient | None = None

async def _get_plan_tracker_client() -> MCPClient | None:
    """plan-tracker MCP server에 연결. 실패 시 None (graceful)."""
    global _client
    if _client is None:
        try:
            _client = MCPClient.from_stdio(os.environ["PLAN_TRACKER_MCP_ENDPOINT"])
            await _client.connect()
        except Exception as e:
            log.warning(f"plan-tracker MCP unavailable: {e}")
            return None
    return _client

async def snapshot_current(domain: str | None = None, ttl_minutes: int = 60) -> dict | None:
    """현재 OKR·KR 스냅샷. 캐시 있음. plan-tracker down 시 None."""
    cache_key = f"okr_snapshot_current:{domain or 'all'}"
    cached = await state.cache_read(cache_key, ttl_minutes)
    if cached:
        return cached

    client = await _get_plan_tracker_client()
    if client is None:
        return None   # graceful degrade

    result = await client.call_tool("okr_snapshot_current", {"domain": domain})
    await state.cache_write(cache_key, result, ttl_minutes)
    return result

async def snapshot_history(weeks: int = 4, domain: str | None = None) -> list[dict] | None:
    client = await _get_plan_tracker_client()
    if client is None:
        return None
    return await client.call_tool("okr_snapshot_history", {"weeks": weeks, "domain": domain})

async def kr_list(domain: str | None = None) -> list[dict] | None:
    client = await _get_plan_tracker_client()
    if client is None:
        return None
    return await client.call_tool("okr_kr_list", {"domain": domain})
```

**`tools/memory.py`** — morning_context 통합:

```python
from tools import okr

async def morning_context() -> dict:
    return {
        "yesterday_daily": await daily(date="yesterday"),
        "unfinished_tasks": await search(query="[ ]", domain=None, since="yesterday"),
        "recent_entity_activity": await entity_activity(since="7 days ago"),
        "user_snippets": await read_user_model_relevant(),
        "domain_okr": await okr.snapshot_current(),  # None이어도 OK (graceful)
    }
```

**`plan-tracker/src/mcp/plan_tracker_server.py`** — 참고 스텁:

```python
from fastmcp import FastMCP
from src.db import get_session
from src.aggregator import snapshot_query

mcp = FastMCP(name="plan-tracker", version="0.1.0")

@mcp.tool()
async def okr_snapshot_current(domain: str | None = None) -> dict:
    """Current KR snapshot from kr_snapshots table."""
    async with get_session() as s:
        snapshots = await snapshot_query.latest_by_kr(s, domain=domain)
    return _group_by_domain(snapshots)

# ... 나머지 도구들

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

## 8. 테스트 포인트

- [ ] 07:00 cron 자동 트리거
- [ ] 수동 `/brief` 호출 즉시 실행
- [ ] 외부(Notion·Codex) 다운시에도 brain/ 기반 축약 브리핑 생성
- [ ] 생성 30초 이내
- [ ] iMessage로 도착
- [ ] brain/daily/.../DD.md에 "🌅 Morning Brief" 섹션 추가
- [ ] 브리핑 끝에 질문 1줄 포함
- [ ] 아첨 표현 없음 ("좋은 아침입니다!" 같은 상투어 없음)
- [ ] **OKR·KR 수치가 우선순위 근거로 인용됨** (정렬 로직 작동)
- [ ] **도메인별 OKR 현황이 "도메인 OKR 주의" 섹션에 반영** (진도 뒤처진 KR 노출)
- [ ] **OKR snapshot 캐싱 동작** (1시간 TTL, 매번 Notion 재호출 안 함)
- [ ] **plan-tracker OKR 영역 매핑 정확** (건강(신체)→health-physical 등)
- [ ] MVP 최소 승리 조건: 실사용에서 "내를 안다" 느낌

---

## 9. 리스크·완화

| 리스크 | 완화 |
|---|---|
| Codex OAuth 장애 | Ollama 로컬로 fallback (품질 조금 낮지만 브리핑 성립) |
| Notion API 장애 | brain/ 기반 부분 브리핑 + "외부 연결 불가" 표시 |
| iMessage 실패 | 터미널 출력 fallback + 로그 |
| 브리핑 너무 길어짐 | 프롬프트에 300자 제한 + 예시로 제약 |
| 사용자가 아침 7시에 자고 있음 | 수동 호출 `mcs brief` 가능. cron 시간 설정으로 조정. |
| 브리핑 무시되는 패턴 지속 | USER.md에 "아침 브리핑 축소" 규칙 추가 가능 |
| **plan-tracker MCP 서버 다운** | graceful degrade — OKR 섹션 생략, 다른 컨텍스트는 정상 |
| **plan-tracker MCP 스키마 변경** | MCP API 버저닝. mcs는 응답 필드 누락 허용. |
| **ML 도메인 OKR이 plan-tracker에 없음** | brain/ 내부에 별도 `brain/okr/ml.md` 파일로 보완 가능 (v1.0) |
| **MCP client connection 실패 (startup)** | 앱은 계속. OKR 호출마다 재연결 시도. |

---

## 10. 관련 FR

- **FR-D2** 대화형 플랜 확정 (응답 이어받기)
- **FR-H3** iMessage (전송 채널)
- **FR-H2** 외부 시스템 읽기 (Notion)
- **FR-B3** 하루 뷰 (yesterday daily 활용)
- **FR-G5** 논리 비약 지적 (브리핑 중 챌린지)

---

## 11. 구현 단계

- **Week 2 Day 5**: morning-brief SKILL.md 초안
- **Week 3 Day 1**: 프롬프트 튜닝
- **Week 3 Day 2**: iMessage 전송 연결
- **Week 4 Day 2**: Hermes cron 등록
- **Week 4 Day 4~7**: 실사용 튜닝 (MVP 최소 승리 조건 검증)
