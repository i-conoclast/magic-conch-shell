# FR-A5: 중복 감지

**카테고리**: A. Capture
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

동일/거의 동일 내용이 중복 저장되지 않음. 특히 파일 watcher와 수동 입력 겹칠 때 중요.

**중복 판정 기준**:
- **완전 일치**: SHA256 해시 동일
- **유사**: 내용 유사도 95% 이상 (임계값 조정 가능)

---

## 2. 관련 컴포넌트

- **Tools**: `memory.check_duplicate`, `memory.similarity`
- **State**: `.brain/state.json` 의 `processed_hashes` 리스트
- **Skills**: 없음 (도구 수준)

---

## 3. 데이터 플로우

```
새 캡처 or ingest 요청 들어옴
   → SHA256 해시 계산
   → state.processed_hashes 조회
     - 일치 → skip + 로그
     - 불일치 → 다음 단계
   → (선택) 최근 N개 메모와 유사도 비교
     - 95% 이상 → 사용자 확인 ("중복인가요?")
        - 예 → skip or 원본 업데이트
        - 아니오 → 저장
     - 95% 미만 → 저장
   → 저장 시 해시 state에 추가
```

---

## 4. 유사도 계산 방법

**1차 (빠름)**: Jaccard 또는 edit distance — 토큰·문자 수준
**2차 (정확)**: 임베딩 코사인 유사도 (memsearch 기존 인프라 활용)

MVP는 1차만. 2차는 필요 시 v1.0.

---

## 5. 의존성·전제

- `.brain/state.json` 존재
- 해시 라이브러리 (Python 표준 `hashlib`)
- memsearch 인덱스 (2차 유사도 시)

---

## 6. 구현 노트

```python
# tools/memory.py
import hashlib

class DuplicateResult(BaseModel):
    is_duplicate: bool
    confidence: float  # 0~1
    original_path: str | None
    reason: str  # "hash-match" | "similarity" | "no-match"

async def check_duplicate(text: str, check_similarity: bool = False) -> DuplicateResult:
    # 1. 해시
    h = hashlib.sha256(text.encode()).hexdigest()
    existing = await state.find_hash(h)
    if existing:
        return DuplicateResult(
            is_duplicate=True,
            confidence=1.0,
            original_path=existing,
            reason="hash-match",
        )

    # 2. 유사도 (옵션)
    if check_similarity:
        similar = await memory.find_similar(text, threshold=0.95, top_k=1)
        if similar:
            return DuplicateResult(
                is_duplicate=True,
                confidence=similar[0]["score"],
                original_path=similar[0]["path"],
                reason="similarity",
            )

    return DuplicateResult(
        is_duplicate=False,
        confidence=0.0,
        original_path=None,
        reason="no-match",
    )

async def mark_processed(text_or_hash: str, path: str):
    h = text_or_hash if len(text_or_hash) == 64 else hashlib.sha256(text_or_hash.encode()).hexdigest()
    await state.add_processed_hash(h, path)
```

### capture 함수에 통합

```python
async def capture(text: str, ..., check_dup: bool = True) -> dict:
    if check_dup:
        dup = await check_duplicate(text, check_similarity=False)  # MVP는 해시만
        if dup.is_duplicate:
            log.info(f"skip duplicate: {dup.original_path}")
            return {"status": "skipped", "reason": dup.reason, "original": dup.original_path}

    # ... 기존 저장 로직
    await mark_processed(text, saved_path)
    return {"path": saved_path, ...}
```

---

## 7. 테스트 포인트

- [ ] 동일 텍스트 두 번 캡처 → 두 번째 skip
- [ ] 텍스트 1글자 다름 → 별개로 저장 (해시 다름)
- [ ] v1.0: 95% 유사 텍스트 → 확인 질문
- [ ] state.json 손상 시 → 재빌드 (FR-I2 연계)
- [ ] 처리 이력이 `mcs doctor`로 조회 가능

---

## 8. 리스크·완화

| 리스크 | 완화 |
|---|---|
| state.json 손상 → 모든 캡처가 새로 보임 | 재빌드 시 brain/ 파일들의 해시로 state 재구축 |
| 정말 의도적인 중복 (같은 생각 강조) | 중복 감지 bypass 옵션 (`--force`) |
| 유사도 95% 임계 부정확 | 설정으로 조정 가능 |

---

## 9. 관련 FR

- **FR-A1** 캡처 (통합 지점)
- **FR-A4** 파일 watcher (주요 사용처)
- **FR-I1** doctor (중복 이력 조회)
- **FR-I2** 인덱스 재빌드 (state 재구축)

---

## 10. 구현 단계

- **Week 1 Day 5**: 해시 기반 중복 체크 + state 저장
- **Week 2 Day 1**: capture·ingest에 통합
- **v1.0**: 유사도 기반 (memsearch 활용)
