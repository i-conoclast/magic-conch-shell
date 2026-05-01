---
name: domain-classify
description: |
  Classify a capture into one of seven canonical domains (career,
  health-physical, health-mental, relationships, finance, ml, general)
  and persist via memory.set_domain. Skips when domain is already set.
  Triggered by the mcs daemon's capture+watcher webhook pipeline; also
  runnable ad-hoc as `/domain-classify <capture-id>`.
metadata:
  hermes:
    tags: [extractor, domain, capture]
    requires_tools:
      - mcp_mcs_memory_show
      - mcp_mcs_memory_set_domain
---

# Domain Classify

캡처 한 건의 도메인을 추정해 frontmatter `domain` 에 박는 스킬. 핵심:
- **이미 도메인 박힌 캡처는 건드리지 않음**. 사용자가 `mcs capture -d career` 로 명시했거나 `brain/domains/career/` 경로에 떨어뜨려서 watcher 가 추론한 값은 신뢰.
- **null 만 갱신**. 잘못 박힌 도메인을 LLM 추정으로 덮어쓰지 않음.
- **확신 없으면 null 유지**. domain 은 검색 필터로만 쓰이니 잘못된 분류가 누락보다 비용이 큼.

## 트리거

- **자동**: mcs daemon 이 `memory.capture()` 또는 watcher `supplement_frontmatter()` 직후 webhook 으로 호출. 페이로드는 entity-extract 와 동일한 `{capture_id, capture_path, type, domain}`.
- **수동**: `/domain-classify <capture-id-or-path>` — 디버깅·리플레이.

## 당신의 역할

- **분류기**. 본문 + (있다면) entities 메타를 보고 7 도메인 중 하나로 분류.
- **민감 도메인 보호**: `health-mental`, `relationships`, `finance` 추정 시 confidence ≥ 0.8 일 때만 set. 0.8 미만은 null 유지 (사용자가 직접 `mcs capture -d` 또는 frontmatter 수정으로 박도록).
- **짧게**. 한 줄 결과 (`✓ career` / `→ unset (low confidence)` / `skipped (already domained)`).

## 도메인 정의 (분류 가이드)

| domain | 신호 |
|---|---|
| `career` | 면접·직장·이력서·포지션·동료·연봉·이직 |
| `health-physical` | 운동·식단·수면·증상·진료·통증·체중 |
| `health-mental` | 감정·번아웃·치료·우울·불안·명상·스트레스 |
| `relationships` | 가족·연인·친구·갈등·소통·관계 변화 |
| `finance` | 지출·수입·투자·세금·예산·자산 |
| `ml` | 모델·임베딩·LoRA·논문·실험·평가·벤치 |
| `general` | 위 어디에도 안 들어가는 일반 메모, 책·취미·여행 등 |

도메인 모호한 경우:
- 면접 합격 후 연봉 협상 → **career** (직장 맥락 우세)
- ML 면접 후기 → **career** (커리어 관련 활동)
- LoRA 논문 리딩 → **ml**
- 운동 후 수면 패턴 변화 → **health-physical**
- 부모 의료비 지출 → **finance** (돈 관련 결정 우세)

## 대화 흐름 (single-shot)

### Phase 1 — 캡처 로드

1. payload 또는 사용자 인자에서 `capture_id` (혹은 `capture_path`) 받음.
2. `mcp_mcs_memory_show(query=id)` 호출.
   - `found=False` → 한 줄 에러 후 종료.
3. 응답에서 `domain` 가 **이미 비어있지 않은 값** 이면:
   - 한 줄: `skipped (already domain=<X>)` 후 종료. set_domain 호출 X.

### Phase 2 — 분류

본문 (body) + entities 메타를 LLM 에 넘겨 다음 JSON 으로 응답 받기:

```json
{"domain": "career", "confidence": 0.92, "rationale": "면접 후기 + 회사명"}
```

또는 분류 안 되는 경우:
```json
{"domain": null, "confidence": 0.40, "rationale": "본문이 너무 짧아 추정 불가"}
```

규칙:
- `domain` 은 7개 또는 null. 다른 문자열 X.
- `confidence` 0~1.
- `rationale` 한 줄 (운영 로그용).

### Phase 3 — 임계값 + 적용

```
if domain is None:
    skip (log: "→ unset (no clear signal)")
elif domain in {"health-mental", "relationships", "finance"} and confidence < 0.8:
    skip (log: "→ unset (sensitive, low confidence)")
elif confidence < 0.6:
    skip (log: "→ unset (low confidence)")
else:
    # `move=true` 면 brain/signals/* 파일은 brain/domains/<X>/ 로 자동 이동.
    # 이미 brain/domains/* 에 있는 파일은 frontmatter 만 업데이트, 이동 X.
    mcp_mcs_memory_set_domain(capture_id=<id>, domain=<X>, move=True)
```

`set_domain` 응답에 `error` 키 있으면 한 줄 보고 후 종료. 응답의 `moved_from` 이 채워져 있으면 종료 출력에 새 경로도 함께 표시.

### Phase 4 — 종료 출력

```
domain-classify · capture=<id>
✓ career (0.92) — 면접 후기 + 회사명
  moved: signals/<id>.md → domains/career/<id>.md
```

이동 안 한 경우 (이미 도메인 폴더에 있거나 skip):
```
domain-classify · capture=<id>
→ unset (low confidence)
```

webhook 자동 트리거에서는 log 로만 보임.

## 규칙

- **set_domain 외 다른 mutation 금지**. body, entities, KR, task — 손대지 말 것.
- **민감 도메인 본문 prompt 노출**: 사용자 자신을 보호하기 위해 본문에서 명백한 식별자 (전화번호·주소·계좌번호·진단명) 가 보이면 prompt 에서 가리고 핵심 단서만 추려 보낼 것.
- **null 캡처는 `general` 강제 X**. 자신 없으면 null 유지.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_show` | Phase 1 캡처 본문 + 메타 로드 |
| `mcp_mcs_memory_set_domain` | Phase 3 도메인 적용 |

## 종료 조건

- 도메인 이미 박힘 → skip 한 줄
- 분류 결과 적용 → 한 줄 결과
- show / set_domain 에러 → 한 줄 에러 후 종료

## 하지 말 것

- **이미 도메인 박힌 캡처 덮어쓰기**.
- **`general` 로 fallback**. null 유지가 정답.
- **본문을 인용해서 다시 capture 만들기**. 이 스킬은 mutation 1개만 (set_domain).
- **entity-extract 의 책임 침범**. 사람·회사 추출은 entity-extract 가 함.

## 자동 트리거 셋업 (1회)

신규 머신 또는 `~/.hermes` 초기화 후 webhook 으로 자동 발동시키려면:

1. **Hermes 쪽** — `webhook` 플랫폼 활성화는 entity-extract 셋업 시 이미 했을 것. 새 라우트만 등록:
   ```bash
   SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
   hermes webhook subscribe domain-classify \
     --skills domain-classify \
     --prompt "Run /domain-classify for capture id={capture_id} path={capture_path} domain={domain}" \
     --description "mcs daemon → FR-A3 domain auto-tag" \
     --deliver log \
     --secret "$SECRET"
   ```

2. **mcs 쪽** — `~/.hermes/.env` 에:
   ```
   MCS_DOMAIN_CLASSIFY_WEBHOOK_ENABLED=true
   MCS_DOMAIN_CLASSIFY_WEBHOOK_ROUTE=domain-classify
   MCS_DOMAIN_CLASSIFY_WEBHOOK_SECRET=<위 SECRET>
   ```
   `mcs daemon stop && start --daemon` 으로 재로딩.

이후로는 `mcs capture "..."` 또는 `brain/signals/` 외부 드롭 → entity-extract + domain-classify 둘 다 병렬 자동.
