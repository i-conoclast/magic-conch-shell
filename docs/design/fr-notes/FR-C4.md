# FR-C4: 엔티티 프로필 조회·수정

**카테고리**: C. Entities
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

엔티티 프로필은 독립 파일. 사용자가 **조회·편집** 가능. 자동 생성 정보와 수동 추가 정보 구분.

---

## 2. 관련 컴포넌트

- **Commands**: `mcs entity show {slug}`, `mcs entity edit {slug}`
- **Tools**: `memory.entity_get`, `memory.entity_update`
- **MCP**: tool 노출

---

## 3. 프로필 구조

`brain/entities/people/jane-smith.md`:
```markdown
---
kind: people
slug: jane-smith
name: Jane Smith
role: ML Recruiter
company: companies/anthropic
relation: professional
first_met: 2026-03-12
last_contact: 2026-04-10
next_followup: 2026-04-25
---

## Context
(사용자 수동)
Anthropic MLE 포지션 리쿠르터.

## Recent
(사용자 수동 or 시스템 보조)
- 2026-04-10: 1차 기술 인터뷰 피드백
- 2026-03-28: 리쿠르터 콜

## Next actions
- 2026-04-25: Follow-up 메일 예정

## Back-links (auto)
<!-- AUTO-GENERATED BELOW. DO NOT EDIT. -->
...
<!-- END AUTO-GENERATED -->

## Manual notes
(자유 작성 — 사용자 전용)
```

**영역 구분**:
- 프론트매터: 자동 + 수동 혼합
- `Context`/`Recent`/`Next actions`: 수동이지만 시스템이 보조 (예: 마지막 접촉일 자동 갱신)
- `Back-links (auto)`: 순수 자동 (주석 경계 엄수)
- `Manual notes`: 순수 수동 (시스템 절대 안 건드림)

---

## 4. CLI

```bash
# 조회
mcs entity show people/jane-smith

# 편집 (외부 에디터 열기)
mcs entity edit people/jane-smith

# 특정 필드 업데이트
mcs entity set people/jane-smith --next-followup 2026-05-01

# 삭제 (주의)
mcs entity delete people/jane-smith --confirm
```

---

## 5. 출력 예시 (조회)

```
$ mcs entity show people/jane-smith
👤 Jane Smith
   Kind:         people
   Role:         ML Recruiter
   Company:      companies/anthropic
   Relation:     professional
   First met:    2026-03-12
   Last contact: 2026-04-10
   Next f/up:    2026-04-25

## Context
Anthropic MLE 포지션 리쿠르터.

## Recent
- 2026-04-10: 1차 기술 인터뷰 피드백
- 2026-03-28: 리쿠르터 콜

## Next actions
- 2026-04-25: Follow-up 메일 예정

## Back-links (6 records)
- 2026-04-19: career/anthropic-mle-1st-round
- 2026-04-10: career/jane-feedback
- ...

[File: brain/entities/people/jane-smith.md]
```

---

## 6. 구현 노트

```python
async def entity_get(slug: str) -> dict | None:
    path = _entity_path_from_slug(slug)
    if not await file.exists(path):
        return None
    post = frontmatter.loads(await file.read(path))
    return {
        "frontmatter": post.metadata,
        "body": post.content,
        "path": path,
    }

async def entity_update(slug: str, frontmatter_patch: dict | None = None, body: str | None = None) -> None:
    path = _entity_path_from_slug(slug)
    post = frontmatter.loads(await file.read(path))
    if frontmatter_patch:
        post.metadata.update(frontmatter_patch)
    if body is not None:
        post.content = body
    post.metadata["updated_at"] = now_kst().isoformat()
    await file.write(path, frontmatter.dumps(post))
```

### 외부 에디터 실행
```python
@app.command(name="entity-edit")
def entity_edit(slug: str):
    path = _entity_path_from_slug(slug)
    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, path])
    # 저장 후 파일 watcher가 자동 감지 → 인덱스 갱신
```

---

## 7. 테스트 포인트

- [ ] `mcs entity show` → 프론트매터 + 섹션 표시
- [ ] `mcs entity edit` → $EDITOR 열림, 저장 시 자동 인덱스 갱신
- [ ] `mcs entity set --next-followup` → 프론트매터 필드 업데이트
- [ ] Manual notes 섹션은 시스템이 건드리지 않음
- [ ] back-link auto 섹션은 재빌드로 갱신되지만 수동 영역은 보존

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 사용자가 주석 경계 실수로 지움 | 편집 후 파싱 실패 시 경고 |
| 프론트매터 필드 순서 뒤바뀜 | python-frontmatter가 알파벳 정렬 유지 |
| 대용량 back-link 섹션 시 프로필 너무 길다 | 기본 최근 10개만, 전체는 `mcs entity backlinks {slug}` |

---

## 9. 관련 FR

- **FR-C1**·**C2** 라이프사이클
- **FR-C3** back-link
- **FR-B4** 타임라인 (프로필 정보 활용)

---

## 10. 구현 단계

- **Week 2 Day 5**: show·get 기본
- **Week 3 Day 1**: edit·set·delete
- **Week 3 Day 2**: 출력 포맷팅 (Rich)
