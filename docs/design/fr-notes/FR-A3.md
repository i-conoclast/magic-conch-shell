# FR-A3: 도메인·엔티티 선택 캡처

**카테고리**: A. Capture
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

FR-A1·A2 캡처 시 **도메인 1개 + 엔티티 N개**를 명시적으로 지정. 지정된 것들은 이후 검색·타임라인 뷰에서 활용.

---

## 2. 관련 컴포넌트

- **Commands**: FR-A1/A2 CLI 옵션 확장 (`-d`, `-e`)
- **Tools**: `memory.capture`, `memory.resolve_entity`
- **MCP**: `memory_capture` 파라미터

---

## 3. 데이터 플로우

```
사용자: mcs capture "Anthropic 면접 리마인드" -d career -e people/jane-smith -e companies/anthropic
   → memory.capture() 호출
   → memory.resolve_entity()가 각 엔티티 slug 검증
     - 존재 → OK
     - 미존재 → 초안 생성 제안 (또는 자동 draft)
   → frontmatter.entities = [resolved slugs]
   → 저장 + back-link 자동 생성 (FR-C3)
```

---

## 4. 입력 포맷

### CLI
```bash
mcs capture "text" -d {domain} -e {entity-slug}... -e ...
mcs capture "text"                     # 무지정 → signals/
mcs capture "text" -d ml               # 도메인만
mcs capture "text" -e people/jane-smith -e companies/anthropic
```

### MCP tool
```python
await memory_capture(
    text="...",
    domain="career",
    entities=["people/jane-smith", "companies/anthropic"],
)
```

### iMessage 자연어 (Hermes 해석)
"Anthropic 면접 리마인드" 같이 도메인·엔티티 언급이 있으면 Hermes가 자동 감지해 MCP tool 호출 시 파라미터로 넣음.

---

## 5. 저장 파일 예시

`brain/domains/career/2026-04-19-142230.md`:
```markdown
---
id: 2026-04-19-142230
type: note
domain: career
entities:
  - people/jane-smith
  - companies/anthropic
created_at: 2026-04-19T14:22:30+09:00
source: typed
---

Anthropic 면접 리마인드
```

---

## 6. 구현 노트

### 엔티티 해상(resolution)
```python
async def resolve_entity(ref: str) -> str:
    """
    ref가 'people/jane-smith' 형식이면 그대로.
    'Jane Smith' 같은 이름이면 엔티티 검색 → slug 매핑.
    미존재 시 draft 생성.
    """
    if "/" in ref:
        # 명시 slug
        if await memory.entity_exists(ref):
            return ref
        else:
            raise EntityNotFound(ref)
    else:
        # 이름 검색
        matches = await memory.entity_search_by_name(ref)
        if len(matches) == 1:
            return matches[0]["slug"]
        elif len(matches) == 0:
            draft = await memory.create_entity_draft(name=ref, kind="people")  # 기본 people 추정
            return draft["slug"]
        else:
            raise AmbiguousEntity(ref, matches)
```

### 도메인 검증
```python
DOMAINS = ["career", "health-physical", "health-mental", "relationships", "finance", "ml", "general"]

def validate_domain(d: str | None) -> str | None:
    if d is None:
        return None
    if d not in DOMAINS:
        raise InvalidDomain(d, suggestions=close_matches(d, DOMAINS))
    return d
```

---

## 7. 테스트 포인트

- [ ] 존재 엔티티 slug 지정 → 정상 저장 + back-link 생성
- [ ] 미존재 엔티티 이름 지정 → draft 엔티티 생성 + 연결
- [ ] 동명이인 2개 존재 → 에러 + 후보 제시 (FR-C5 연계)
- [ ] 잘못된 도메인 (`careeer` 오타) → 유사 도메인 제안
- [ ] 엔티티 미지정 + 도메인만 → 도메인 폴더에 저장

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 사용자가 존재 여부 모르고 이름만 적으면 draft 남발 | 자동 draft 생성은 OK (저녁 회고에서 승인 처리) |
| 타이핑 slug 오타 (`people/jane-smity`) | 퍼지 매칭 + 제안 |
| 도메인 이름 한글로 적을 경우 | 영어 slug만 허용. 한글 시 안내. |

---

## 9. 관련 FR

- **FR-A1·A2** 캡처 경로 확장
- **FR-C1** 자동 엔티티 draft
- **FR-C3** back-link 자동 생성
- **FR-C5** 동명이인 처리
- **FR-B2** 도메인·엔티티 필터 검색 (입력된 정보 활용)

---

## 10. 구현 단계

- **Week 1 Day 4**: `-d`/`-e` 옵션 CLI에 추가
- **Week 1 Day 5**: 엔티티 해상 로직 + draft 생성 연계
- **Week 2 Day 3**: iMessage 자연어에서 도메인·엔티티 추출 (Hermes)
