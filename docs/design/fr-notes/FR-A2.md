# FR-A2: 구조화 기록 캡처

**카테고리**: A. Capture
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

면접·회의·한 주 실험 진행 같은 반복 패턴의 기록을 **템플릿 기반**으로 작성. 자유 메모(FR-A1)와 달리 **필드 구조**가 있음.

**초기 템플릿 (MVP)**:
- 면접 후기 (`templates/interview-note.md`)
- 회의록 (`templates/meeting-note.md`)
- 실험·학습 진행 로그 (`templates/experiment-log.md`)

---

## 2. 관련 컴포넌트

- **Commands**: `/capture-structured`, `mcs capture --template <type>`
- **Tools**: `memory.capture_structured`, `file.read_template`
- **Skills**: 없음 (템플릿 처리는 도구 수준)
- **MCP**: `memory_capture_structured` tool

---

## 3. 데이터 플로우

```
사용자: /capture-structured interview
   → mcs가 templates/interview-note.md 읽음
   → 사용자에게 필드 프롬프트 (회사·면접관·핵심 결론·다음 단계)
   → 사용자 채움 (비어도 저장 가능)
   → frontmatter에 type=interview-note + 필드 값
   → brain/domains/career/YYYY-MM-DD-{slug}.md 저장
   → entity-extract skill 호출 (면접관 이름 → people draft)
```

---

## 4. 템플릿 포맷

`templates/interview-note.md`:
```markdown
---
template: interview-note
domain: career
fields:
  - name: company
    type: entity-ref
    kind: companies
    required: false
  - name: interviewers
    type: entity-ref-list
    kind: people
    required: false
  - name: round
    type: enum
    values: [1차, 2차, 3차, final]
  - name: format
    type: enum
    values: [온라인, 오프라인, 전화]
  - name: impression
    type: text
  - name: next_steps
    type: text
---

# Interview Note Template

## Required sections when saved

- Company
- Interviewers
- Round
- Key topics
- Impression
- Next steps
- Follow-up actions
```

저장된 기록:
```markdown
---
id: 2026-04-19-anthropic-mle-1st-round
type: note
template: interview-note
domain: career
company: companies/anthropic
interviewers: [people/jane-smith]
round: 1차
format: 온라인
created_at: 2026-04-19T14:22:00+09:00
source: typed
---

## Key topics
LoRA 구현, prompt engineering, eval harness

## Impression
Jane은 질문이 구체적. 팀 문화는 개방적.

## Next steps
Jane이 내부 피드백 공유 후 2차 일정 알려주기로.

## Follow-up actions
- [ ] Follow-up 메일 발송 (4/25 전)
- [ ] LoRA 코드 공유
```

---

## 5. 의존성·전제

- `templates/` 디렉토리와 3개 기본 템플릿 존재
- FR-A1 저장 인프라 (capture core) 먼저 구현
- FR-C1 엔티티 초안 자동 생성 (interviewers 필드 활용)

---

## 6. 구현 노트

### CLI 구현
```python
@app.command()
def capture_structured(
    template: str = typer.Argument(..., help="Template name"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive"),
) -> None:
    """Capture a structured record using a template."""
    tpl = file.read_template(template)
    values = {}
    for field in tpl["fields"]:
        if interactive:
            values[field["name"]] = typer.prompt(field["name"], default="")
    memory.capture_structured(template=template, fields=values)
```

### 핵심 로직 (tools/memory.py)
```python
async def capture_structured(template: str, fields: dict) -> dict:
    tpl = await file.read_template(template)
    frontmatter = {
        **tpl["default_frontmatter"],
        "id": generate_slug(fields),
        "template": template,
        "created_at": now_kst().isoformat(),
        **extract_entity_refs(fields, tpl),
        **fields,
    }
    path = determine_path(frontmatter["domain"], frontmatter["id"])
    body = render_structured_body(tpl, fields)
    await file.write(path, assemble(frontmatter, body))

    # 엔티티 초안 생성
    for entity_field in tpl.get("entity_fields", []):
        values = fields.get(entity_field["name"], [])
        for v in (values if isinstance(values, list) else [values]):
            if v and not await memory.entity_exists(v):
                await memory.create_entity_draft(kind=entity_field["kind"], name=v)

    return {"path": path, "id": frontmatter["id"]}
```

---

## 7. 테스트 포인트

- [ ] 기본 3종 템플릿 로드·파싱 정상
- [ ] 필드 일부만 채워도 저장 성공
- [ ] 새 템플릿 `.md` 추가 시 재시작 없이 목록에 등장
- [ ] 면접 후기 저장 → 면접관 이름이 엔티티 초안으로 등록
- [ ] iMessage에서 "면접 후기 저장" 호출 시 Hermes가 적절한 skill 호출

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 템플릿 필드가 많으면 입력 부담 | 전부 optional. 최소 제목만 있어도 저장. |
| 템플릿 포맷 문법 오류 | `mcs template validate {name}`로 검증. 로드 실패 시 다른 템플릿엔 영향 없음 (격리). |
| 사용자가 템플릿 대신 자유 메모로 쓰고 싶을 때 | `/capture`로 우회. 템플릿 강제 안 함. |
| 엔티티 필드에 쓴 이름이 기존 엔티티와 약간 다름 (예: "Jane" vs "Jane Smith") | 모호하면 승인 인박스에 "기존 X와 같은가요?" 제안 (FR-C5). |

---

## 9. 관련 FR

- **FR-A1** 자유 메모 캡처 (대조 경로)
- **FR-A3** 도메인·엔티티 선택 (A2는 템플릿 내에서 자동)
- **FR-C1** 엔티티 초안 자동 생성
- **FR-E4** DIY 템플릿 추가 (사용자가 새 템플릿 작성)

---

## 10. 구현 단계

- **Week 1 Day 3**: 기본 3 템플릿 작성 + 템플릿 로더
- **Week 1 Day 4**: `mcs capture-structured` 인터랙티브 CLI
- **Week 2 Day 3**: iMessage에서 "면접 저장" 자연어 감지 → Hermes skill → MCP tool 호출
