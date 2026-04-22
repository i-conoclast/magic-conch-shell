# FR-G2: 자동 엔티티 태깅

**카테고리**: G. Evolution
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

기록·대화·세션 결과에서 언급된 엔티티 **자동 태그 연결**. 신규 엔티티면 초안 생성(FR-C1), 기존이면 연결(FR-C3).

---

## 2. 관련 컴포넌트

- **Skills**: `entity-extract` (FR-C1 재사용)
- **Tools**: `memory.auto_tag`
- **Trigger**: 파일 저장 이벤트 (FR-A1·A4·D5·G1)

---

## 3. 데이터 플로우

```
저장 완료 이벤트 (캡처·플랜·세션 로그)
   → 파일 본문 읽기
   → 이미 알려진 엔티티 이름 스캔 (dictionary 기반 빠른 매칭)
   → 매치된 엔티티를 frontmatter.entities에 추가 (기존 + 새로)
   → back-link 추가 (FR-C3)
   → LLM 기반 엔티티 감지 (FR-C1)도 병행 → 신규 draft
   → 저녁 회고에 초안 항목 추가
```

---

## 4. 빠른 매칭 (dictionary)

```python
async def build_entity_dictionary() -> dict[str, str]:
    """Returns: {entity_name: slug, ...}. 캐시해서 반복 사용."""
    entities = await memory.all_entities()
    d = {}
    for e in entities:
        d[e["name"].lower()] = e["slug"]
        # 별명·부분 이름도
        parts = e["name"].split()
        if len(parts) > 1:
            d[parts[0].lower()] = e["slug"]  # "Jane" → people/jane-smith
    return d

async def auto_tag(text: str, existing_entities: list[str]) -> list[str]:
    dictionary = await build_entity_dictionary()
    detected = set(existing_entities)
    for name, slug in dictionary.items():
        if name in text.lower():
            detected.add(slug)
    return list(detected)
```

---

## 5. LLM 기반 (신규 감지)

- FR-C1의 entity-extract skill 재사용
- dictionary 기반 빠른 매칭과 **병행 실행** (서로 보완)

---

## 6. 테스트 포인트

- [ ] 기록에 "Jane과 미팅" → people/jane-smith 자동 추가 (frontmatter + back-link)
- [ ] "Jane Smith" 정식 이름도 매치
- [ ] "jane"만 있으면 매치 (부분 이름)
- [ ] 알려지지 않은 이름 → 초안 생성 (FR-C1)
- [ ] 중복 태깅 방지 (이미 있으면 skip)
- [ ] 저장 후 몇 초 내 반영

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| "Jane"이 사람 이름 아닌 경우 (brand 등) | 신뢰도 체크, 문맥상 역할 키워드 확인 |
| 부분 이름 매치 남용 (John → people/john-doe 오탐) | 매칭 전에 최소 2글자 + 대소문자 부합성 체크 |
| dictionary가 많아져 느림 | 메모리 캐시 + 해시 |

---

## 8. 관련 FR

- **FR-C1** 초안 생성
- **FR-C3** back-link
- **FR-A1·A4·D5·G1** 저장 이벤트 트리거

---

## 9. 구현 단계

- **Week 2 Day 7**: dictionary 기반 빠른 매칭
- **Week 3 Day 1**: 저장 훅 연결
- **Week 3 Day 2**: FR-C1 (LLM) 병행
