# FR-G4: 사용자 모델 (열람·수정 가능)

**카테고리**: G. Evolution
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

시스템이 학습한 **사용자 패턴·선호**는 `brain/USER.md` 파일에 저장. 사용자가 **언제든 열람·편집**. 블랙박스 금지.

---

## 2. 관련 컴포넌트

- **File**: `brain/USER.md` (symlink `USER.md` via 루트)
- **Tools**: `memory.user_model_read`, `memory.user_model_update`
- **Skills**: 주간 리뷰에서 패턴 감지 → USER.md 업데이트 제안

---

## 3. USER.md 구조

(이미 설치됨) 6 섹션:
1. **Identity** (수동)
2. **Life Rhythm** (auto)
3. **Preferences** (auto)
4. **Tone Preferences** (auto)
5. **Manual Rules** (수동, 시스템 수정 금지)

---

## 4. 자동 학습 업데이트

주간 리뷰·저녁 회고 중에:
```
지난주 아침 접점 시각 평균: 07:15
  → USER.md "Life Rhythm > Morning contact window" 갱신

지난 4주 거절 패턴: 주말 학습 세션 3/4 거절
  → USER.md "Preferences > Rejected Suggestion Patterns"에 추가

지난주 오라클 선택: "No." 5회, "Nothing." 3회
  → USER.md "Tone Preferences > Preferred oracle answers" 업데이트
```

**승인 필수**:
```
"USER.md에 이번 주 학습된 항목 3개 갱신할까요?
 - Life Rhythm: 아침 07:15
 - ...
 [승인] [거절] [내용 보기]"
```

---

## 5. 수동 편집 보존

"Manual Rules" 섹션은 **HTML 주석으로 경계**:
```markdown
## Manual Rules (user-authored)

<!-- Anything below is user-authored. The agent does not overwrite this section. -->

- No finance challenges on weekends.
- Always route family-related suggestions through the evening retro.
```

시스템이 USER.md 수정할 때:
- Manual Rules 섹션 아래는 **절대 건드리지 않음**
- 자동 섹션만 갱신
- 편집 전 파일 hash 기록 → 사용자 수동 편집 감지 시 충돌 확인

---

## 6. 구현 노트

```python
async def user_model_update(section: str, patch: str) -> dict:
    if section == "Manual Rules":
        raise PermissionError("Manual Rules section is user-authored only")

    content = await file.read("brain/USER.md")
    new_content = _replace_section(content, section, patch)
    await file.write("brain/USER.md", new_content)
    return {"section": section, "updated": True}

async def user_model_read(section: str | None = None) -> dict:
    content = await file.read("brain/USER.md")
    if section:
        return {"section": section, "content": _extract_section(content, section)}
    return {"full": content}
```

---

## 7. CLI

```bash
# 조회
mcs user show
mcs user show --section "Life Rhythm"

# 편집 (외부 에디터)
mcs user edit

# 수동 rule 추가
mcs user add-rule "No work after 22:00"
```

---

## 8. 테스트 포인트

- [ ] 주간 리뷰 후 USER.md 자동 섹션 갱신 (승인 후)
- [ ] Manual Rules 섹션은 시스템이 건드리지 않음 (테스트: 수정 시도 → PermissionError)
- [ ] 사용자가 외부 에디터로 USER.md 수정 → 다음 시스템 참조에 반영
- [ ] 충돌 감지 (시스템 수정 중에 사용자가 편집) → 알림

---

## 9. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 사용자가 주석 경계 실수로 지움 | 편집 후 파싱 + 경계 없음 감지 시 경고 |
| 자동 학습 잘못된 항목 | 승인 필수 + 사용자가 삭제 가능 |
| symlink 깨짐 | 루트 `USER.md` 심볼릭링크 유효성 `mcs doctor` 체크 |

---

## 10. 관련 FR

- **FR-D4** 주간 리뷰 (학습 업데이트 발동 지점)
- **FR-G3** 제안 인박스 (USER.md 갱신 제안도 여기)
- **FR-F1** 톤 판단 (USER.md "Tone Preferences" 참조)

---

## 11. 구현 단계

- **Week 3 Day 1**: user_model_read/update 기본
- **Week 4 Day 1**: 주간 리뷰와 통합 (갱신 제안)
- **v1.0**: 학습 정확도 향상
