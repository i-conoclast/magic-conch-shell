---
name: entity-extract
description: |
  Extract named entities (people / companies / jobs / books) from a
  freshly written capture and stage drafts under brain/entities/drafts/.
  Idempotent — entities that already exist (active or draft) get a
  back-link instead of a new draft. Triggered by the mcs daemon's
  capture→webhook pipeline (FR-C1) and runnable ad-hoc with a capture
  id. Confidence < 0.7 entries are dropped to keep the approval inbox
  signal-heavy.
metadata:
  hermes:
    tags: [extractor, entities, capture]
    requires_tools:
      - mcp_mcs_memory_show
      - mcp_mcs_memory_entity_get
      - mcp_mcs_memory_entity_create_draft
      - mcp_mcs_memory_entity_add_backlink
---

# Entity Extract

캡처 본문에서 사람·회사·면접 포지션·책 같은 **고유명사**를 뽑아 brain/entities/drafts/ 에 초안으로 박는 스킬. 사용자 승인은 evening-retro 가 받음 — 이 스킬은 **절대 confirm 하지 않는다**.

## 트리거

- **자동 (정상 경로)**: mcs daemon 이 `memory.capture()` 직후 webhook 으로 호출. 페이로드는 `{capture_id, capture_path, domain, source}`.
- **수동 (디버그/리플레이)**: `/entity-extract <capture-id-or-path>` — Hermes REPL 에서 직접 호출.

## 당신의 역할

- **정확도 우선**. confidence < 0.7 은 무조건 drop. 누락은 retro 시점에 사용자가 보완 가능.
- **노이즈 차단**. 일반명사 / 직무 일반어 / 흔한 단어("recruiter", "회사", "팀") 는 엔티티 아님.
- **중복 방지**. 같은 이름이 active 또는 draft 로 이미 있으면 새 초안 만들지 말고 back-link 만 추가.
- **민감 도메인 주의**. capture 의 `domain` 이 `finance` / `health-physical` / `health-mental` / `relationships` 면 인물·관계 추출은 하되, 본문을 그대로 prompt 에 노출하지 말고 이름·역할만 추려서 보내기.

## 대화 흐름 (single-shot)

### Phase 1 — 캡처 로드

1. payload 또는 사용자 인자에서 `capture_id` 또는 `capture_path` 를 받는다.
   - `id` 만 있으면 `mcp_mcs_memory_show(query=id)` 로 본문/도메인/엔티티 메타 조회.
   - 결과 `found=False` 면 `"capture not found: <id>"` 한 줄로 종료.

2. 본문 + frontmatter 로 추출 컨텍스트 만들기:
   - `text` = capture body
   - `domain` = frontmatter.domain
   - `existing_entities` = frontmatter.entities (이미 사람이 manual `-e` 로 묶은 것)

### Phase 2 — LLM 추출

다음 JSON schema 로 응답하도록 강제. 같은 카테고리 안에서도 confidence 따로.

```json
{
  "people":    [{"name": "Jane Smith", "role": "ML Recruiter", "confidence": 0.95}],
  "companies": [{"name": "Anthropic", "url": "anthropic.com", "confidence": 0.98}],
  "jobs":      [{"name": "Anthropic MLE", "company": "Anthropic", "confidence": 0.85}],
  "books":     [{"name": "Speech and Language Processing", "author": "Jurafsky", "confidence": 0.90}]
}
```

추출 가이드라인 (프롬프트로 모델에 전달):
- 본문에서 **명시적으로 이름이 등장**한 경우만 — "그 사람", "거기" 같은 대명사 X.
- **사람**: 풀네임 또는 한국 이름 2자+ / 영어 first+last 패턴. 직책 형용어("디렉터", "엔지니어")만 있고 이름이 없으면 X.
- **회사**: 고유명. "회사" / "스타트업" / "팀" 같은 일반명사 X. 아주 잘 알려진 약칭(예: "Apple")은 OK.
- **jobs**: `{회사}-{역할}` 패턴 또는 본문에서 명시된 포지션명. 정규 응시 중인 자리만.
- **books**: 책 / 논문 / 강의자료 제목. 따옴표·이탤릭으로 묶인 것 우선.
- 한국어 capture 면 한국어 이름·회사명도 동일하게 다룸.
- `existing_entities` 에 이미 있는 slug 는 응답에서 제외 (호출자가 이미 알고 있음 → 그쪽에 back-link 만 다시 박을 것).
- 모든 항목에 `confidence` (0~1) 부여. 0.7 미만은 응답에 넣지 말 것.

### Phase 3 — 분류 + draft 생성

응답 받은 후 카테고리별로 순회 (mapping: people → kind="people", companies → "companies", jobs → "jobs", books → "books"):

각 항목에 대해:

1. slug 후보 = 이름을 lowercase / 공백→hyphen / 한글 보존. ASCII 외 특수문자 제거.
2. `mcp_mcs_memory_entity_get(slug="<kind>/<slug>")` 호출.
   - `found=True` (active 또는 draft) → 기존 엔티티 → `mcp_mcs_memory_entity_add_backlink(slug=qualified, record_path=capture_path)`. 새 draft 안 만듦.
   - `found=False` → 새 draft 후보. Phase 4 로.

### Phase 4 — Draft 박기

`mcp_mcs_memory_entity_create_draft(...)` 호출:

```
kind: people | companies | jobs | books
name: <원본 이름 그대로>
detected_at: <지금 KST ISO>
detection_confidence: <0.7~1.0>
promoted_from: <capture rel_path>
extra: { role / company / url / author / ... }   # kind 별로 알맞은 필드만
```

**KR.current 같은 거 절대 건들지 말 것.** (per `feedback_kr_current_owner`.)

### Phase 5 — 종료 출력

운영 계열 관측용 짧은 1~3 줄 요약:

```
entity-extract · capture=<id> · drafts=2 · backlinks=1 · skipped(low-conf)=3
- new draft: people/jane-smith (0.95)
- new draft: companies/anthropic (0.98)
- backlink:  books/speech-and-language-processing
```

webhook 자동 트리거 케이스에서는 `--deliver none` 으로 등록되므로 stdout 만으로 충분. Hermes 가 JSON 응답 보존하니 디버깅 가능.

## 사용 가능한 MCP 도구

| 도구 | 용도 |
|---|---|
| `mcp_mcs_memory_show` | Phase 1 capture 본문/메타 로드 |
| `mcp_mcs_memory_entity_get` | Phase 3 중복 체크 |
| `mcp_mcs_memory_entity_create_draft` | Phase 4 새 초안 생성 |
| `mcp_mcs_memory_entity_add_backlink` | Phase 3 기존 엔티티에 백링크 |

## 종료 조건

- capture not found → 한 줄 에러 후 종료
- 추출 결과 0개 → "no entities" 한 줄 후 종료
- draft / backlink 작업 부분 실패 → 가능한 항목까지 처리 후 결과에 `errors:` 배열로 명시

## 하지 말 것

- **confirm / promote**. 그건 evening-retro 권한.
- **삭제 / merge**. FR-C5 는 별도 흐름.
- **KR.current 업데이트**. 데이터 흐름은 capture↔task↔kr 만.
- **본문 일부를 LLM 재요약해서 capture 에 다시 쓰기**. 이 스킬은 **읽기 전용 + 신규 draft** 만.
- **민감 도메인 본문 평문 prompt 노출**. 이름·역할만 추려서 호출.
- **confidence < 0.7 항목 draft**. 무조건 drop.

## 참고

- 데이터 모델: `docs/design/fr-notes/FR-C1.md`
- 스킬 컨벤션: `feedback_extractor_skill_path` (이 디렉토리 위치 자체가 룰)
- 트리거 메커니즘: Hermes webhook-subscriptions (mcs `feedback_hermes_trigger_via_webhook` 참조)

## 자동 트리거 셋업 (1회)

신규 머신 / `~/.hermes` 초기화 후에는 두 단계 필요:

1. **Hermes 쪽** — webhook 플랫폼 켜고 라우트 등록:
   ```bash
   # ~/.hermes/config.yaml 에 platforms.webhook.enabled: true + port: 8644 추가
   hermes gateway restart
   SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
   hermes webhook subscribe entity-extract \
     --skills entity-extract \
     --prompt "Run /entity-extract for capture id={capture_id} path={capture_path} domain={domain} type={type}" \
     --description "mcs daemon → FR-C1 entity drafts" \
     --deliver log \
     --secret "$SECRET"
   ```

2. **mcs 쪽** — `~/.hermes/.env` 에 같은 secret 박기 (mcs.config 가 이 파일을 fallback 으로 읽음):
   ```
   MCS_ENTITY_EXTRACT_WEBHOOK_ENABLED=true
   MCS_ENTITY_EXTRACT_WEBHOOK_ROUTE=entity-extract
   MCS_ENTITY_EXTRACT_WEBHOOK_SECRET=<위에서 만든 SECRET>
   ```
   그리고 `mcs daemon stop && mcs daemon start --daemon` 으로 재로딩.

이후로는 `mcs capture "..."` 한 줄이 → webhook → 이 스킬 → drafts/ 까지 자동.
