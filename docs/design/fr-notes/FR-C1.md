# FR-C1: 자동 엔티티 초안 생성

**카테고리**: C. Entities
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

기록에서 새 고유명사(사람·회사·직무·책) 감지 시 **초안 엔티티** 자동 생성. 사용자 요청 없이.

초안은 `brain/entities/drafts/{kind}/`에 저장되고, 저녁 회고 승인 대기열로 들어감.

---

## 2. 관련 컴포넌트

- **Skills**: `entity-extract` (주)
- **Tools**: `memory.entity_detect`, `memory.create_entity_draft`
- **MCP**: `memory_entities_list`, `memory_entity_create`
- **의존**: 캡처 후 비동기 발동 (FR-A1, FR-A4)

---

## 3. 데이터 플로우

```
FR-A1/A4에서 새 기록 저장 완료
   → asyncio.create_task(hermes.run_skill("entity-extract", {"path": ...}))
   → Hermes가 skills/entity-extract/SKILL.md 실행
     1. MCP tool: memory_read(path) — 기록 본문 읽기
     2. LLM call (ollama-local, 민감도 따라 판단)
        - 프롬프트: "본문에서 사람·회사·직무·책 이름을 추출"
        - 응답: {people: [...], companies: [...], ...}
     3. 각 이름에 대해:
        a. memory_entity_exists() 확인
        b. 기존 엔티티면 skip (이미 태깅됨 — FR-G2)
        c. 미존재 + 신뢰도 ≥ threshold → create_entity_draft()
        d. 신뢰도 낮음 → 스킵 (false positive 방지)
   → 초안은 approval-inbox.jsonl에 항목 추가 (FR-G3)
```

---

## 4. 감지 로직

LLM 프롬프트 예시:
```
You read the following memo and extract named entities of these kinds:
- people (real people's names, often accompanied by roles or relations)
- companies (company/organization names)
- jobs (specific job postings/applications, typically {company}-{role})
- books (book titles)

Return JSON with confidence scores (0~1).
Only include entities with confidence >= 0.7.
Ignore generic terms.

Memo:
<memo text>

Return:
{
  "people": [{"name": "Jane Smith", "role": "ML Recruiter", "confidence": 0.95}],
  "companies": [{"name": "Anthropic", "confidence": 0.98}],
  "jobs": [],
  "books": []
}
```

---

## 5. Draft 파일 예시

`brain/entities/drafts/people/jane-smith.md`:
```markdown
---
kind: people
slug: jane-smith
name: Jane Smith
role: ML Recruiter  # 추출된 정보
status: draft
promoted_from: brain/domains/career/2026-04-19-anthropic-mle-1st-round.md
detected_at: 2026-04-19T14:30:00+09:00
detection_confidence: 0.95
---

## Context
_(승인 시 작성)_

## Recent
- 2026-04-19: 첫 언급 (1차 면접 후기)

## Back-links (auto)
- [[domains/career/2026-04-19-anthropic-mle-1st-round]]
```

---

## 6. 구현 노트

### SKILL.md
`skills/entity-extract/SKILL.md`:
```markdown
---
name: entity-extract
description: Detect named entities in a captured note and create drafts if new
trigger:
  - event: on_capture
tools: [memory, llm]
model: ollama-local
sensitive: false
---

# Entity Extract

## Steps
1. Read the captured file via memory_read
2. Call llm.call with the extraction prompt (see prompt.md)
3. For each detected entity:
   - Check if exists via memory_entities_list
   - If new and confidence >= 0.7, call memory_entity_create(kind, name, role, ...)
   - If exists, link via memory_note_link_entity
4. Add drafts to approval inbox

## References
- [prompt.md](prompt.md)
```

### Core
```python
async def create_entity_draft(kind: str, name: str, **fields) -> dict:
    slug = slugify(name)  # "Jane Smith" → "jane-smith"
    path = f"brain/entities/drafts/{kind}/{slug}.md"

    if await file.exists(path):
        return {"status": "exists_draft", "path": path}

    frontmatter = {
        "kind": kind,
        "slug": slug,
        "name": name,
        "status": "draft",
        "detected_at": now_kst().isoformat(),
        **fields,
    }
    body = "## Context\n_(to be filled on approval)_\n\n## Back-links (auto)\n"
    await file.write(path, assemble(frontmatter, body))

    # approval-inbox에 추가 (FR-G3)
    await state.add_approval_item({
        "type": "entity-draft",
        "path": path,
        "kind": kind,
        "name": name,
        "detected_at": frontmatter["detected_at"],
    })
    return {"status": "created", "path": path}
```

---

## 7. 테스트 포인트

- [ ] "Jane Smith, ML Recruiter 만났음" → people/jane-smith 초안
- [ ] 기존 엔티티 언급 → 초안 생성 X, 연결만 (FR-G2)
- [ ] 모호한 감지 (confidence < 0.7) → 초안 생성 X
- [ ] 이미 초안 존재 → 중복 생성 X
- [ ] 초안이 approval-inbox.jsonl에 기록됨
- [ ] 저녁 회고에서 초안 목록 보임 (FR-D3·G3)

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| LLM false positive (엉뚱한 단어 엔티티로) | confidence ≥ 0.7 + 수동 승인 필수 |
| LLM false negative (놓침) | 사용자가 수동 `mcs entity create` 가능 (FR-C4) |
| 같은 이름 다른 사람 감지 → 동명이인 충돌 | FR-C5 병합·분리 워크플로 |
| 한국어 이름 감지 품질 | Qwen3 한국어 NER 성능 Week 1~2 검증 |
| 로컬 LLM 부담 (매 캡처마다 호출) | 배치 처리 옵션 (n개 모아서 한 번) |

---

## 9. 관련 FR

- **FR-A1·A4** 캡처 (발동 지점)
- **FR-C2** 승인·거절 (저녁 회고)
- **FR-C3** back-link 생성
- **FR-G2** 자동 태깅 (기존 엔티티 연결)
- **FR-G3** 제안 인박스

---

## 10. 구현 단계

- **Week 2 Day 3**: entity-extract SKILL.md 작성
- **Week 2 Day 4**: 프롬프트 튜닝 + JSON 출력 파싱
- **Week 3 Day 1**: 초안 생성 + approval-inbox 연동
- **Week 3 Day 2**: 저녁 회고 통합 테스트
