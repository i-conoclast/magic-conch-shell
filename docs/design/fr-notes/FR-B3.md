# FR-B3: 하루 단위 뷰 (일지)

**카테고리**: B. Memory
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

특정 날짜의 기록·브리핑·회고를 **시간순으로 한 번에** 조회. 하루 통합 파일 `brain/daily/YYYY/MM/DD.md` 활용.

---

## 2. 관련 컴포넌트

- **Commands**: `mcs daily [date]`
- **Tools**: `memory.daily`, `file.read`
- **Skills**: morning-brief·evening-retro가 이 파일에 쓰기
- **MCP**: `memory_daily` tool

---

## 3. 데이터 플로우

```
mcs daily "어제"
   → 상대 표현 파싱 → YYYY-MM-DD 절대 날짜
   → brain/daily/YYYY/MM/DD.md 읽기
     - 있으면: 파일 반환 (브리핑·엔트리·회고 섹션 모두)
     - 없으면: 해당 날짜 signals/·domains/ 에서 조회 후 합성
   → 시간순 정렬
   → 결과 표시
```

---

## 4. 상대 날짜 표현

- `today`, `오늘` → 오늘
- `yesterday`, `어제` → 1일 전
- `지난 금요일`, `last Friday` → 가장 가까운 지난 금요일
- `3 days ago`, `3일 전` → 3일 전
- `2026-04-15` 절대 날짜

---

## 5. 표시 포맷

```
$ mcs daily 어제
📅 2026-04-18 (금요일)

🌅 Morning Brief (07:15)
  Today priorities: Anthropic follow-up, ML study
  Yesterday missed: (none)
  Question: "How's the Jane follow-up feeling?"

📝 Entries (8)
  08:32  signals/  "머리 복잡. 정리 필요"
  09:15  career/   "Jane한테 follow-up 메일 초안"
  12:40  ml/       "LoRA 논문 섹션 3 읽음"
  14:22  career/   "Jane 답장: 2차 일정 조율 중"
  15:10  ml/       "prompt engineering 정리"
  ...

🌙 Evening Retro (22:30)
  Completed: 3/5
  Approved entities: jane-smith
  Tomorrow memo: 블로그 초안 오전 1시간

[Open full file: brain/daily/2026/04/18.md]
```

---

## 6. 구현 노트

```python
async def daily(date: str | date = "today") -> dict:
    target = parse_date(date)  # 상대 표현 지원
    path = f"brain/daily/{target.year:04d}/{target.month:02d}/{target.day:02d}.md"

    if await file.exists(path):
        post = frontmatter.loads(await file.read(path))
        return {
            "date": target.isoformat(),
            "path": path,
            "frontmatter": post.metadata,
            "sections": parse_daily_sections(post.content),
        }

    # 파일 없으면 signals/domains에서 합성
    entries = await memory.list_by_date(target)
    return {
        "date": target.isoformat(),
        "path": None,
        "frontmatter": None,
        "sections": {"entries": entries},
    }

def parse_date(expr: str) -> date:
    """
    "today" / "어제" / "지난 금요일" / "2026-04-15" 등 파싱.
    """
    if expr in ("today", "오늘"):
        return date.today()
    if expr in ("yesterday", "어제"):
        return date.today() - timedelta(days=1)
    # ... 기타 패턴
    return date.fromisoformat(expr)
```

---

## 7. 테스트 포인트

- [ ] `mcs daily` → 오늘
- [ ] `mcs daily 어제`
- [ ] `mcs daily 2026-04-15`
- [ ] 브리핑·회고 없는 날도 정상 표시 (엔트리만)
- [ ] 기록 0건 날짜 → "기록 없음" 메시지
- [ ] 대용량 일지 (~100 entries) 표시 가독성

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| daily 파일이 거대해지면 가독성↓ | 섹션별 접기·`--section entries` 옵션 |
| 시간순 정렬 시 일부 프론트매터 누락 | 누락 시 파일 수정 시각 fallback |

---

## 9. 관련 FR

- **FR-D1** 아침 브리핑 (daily에 쓰기)
- **FR-D3** 저녁 회고 (daily에 쓰기)
- **FR-B1** 검색
- **FR-B4** 엔티티 타임라인 (유사한 시간 기반 뷰)

---

## 10. 구현 단계

- **Week 1 Day 6**: 기본 daily 읽기
- **Week 1 Day 7**: 상대 표현 파싱
- **Week 3 Day 1**: 브리핑·회고 자동 포함 (daily 섹션 구조화)
