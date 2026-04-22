# FR-H4: 이메일 자동 수집 (v1.0)

**카테고리**: H. Integration
**우선순위**: 중간 (**MVP 범위 밖**, v1.0에서 구현)

---

## 1. Overview

지정한 필터에 맞는 이메일을 자동 수집. 취업·채용·중요 공지 등.

**MVP 범위 밖.** 스펙만 미리 정의.

---

## 2. v1.0 계획

### 대상 메일 서비스
- Gmail (우선) — IMAP / Gmail API
- Apple Mail (차선) — 로컬 DB 접근

### 필터 방식
```yaml
# config.yaml
email_filters:
  - name: anthropic-jobs
    from: ["recruiter@anthropic.com", "jobs@anthropic.com"]
    subject_contains: []
    folder: "INBOX"
    domain: career
    create_entity: companies/anthropic
  - name: financial-statements
    from: ["statements@*"]
    subject_regex: "(statement|bill)"
    domain: finance
    sensitive: true
```

### 수집 흐름
```
cron 시간 (예: 매시)
   → Gmail API: 새 메일 중 필터 매치
   → 각 매치:
     1. memory.capture_structured(template=email-note, ...)
     2. entity-extract skill 호출
   → 수집 결과 로그 + 다음 브리핑에 언급
```

### 개인정보
- 민감 도메인(finance 등)은 로컬 처리만
- 외부 LLM 안 씀

---

## 3. 데이터 구조

```markdown
---
id: 2026-04-19-email-anthropic-followup
type: note
template: email-note
domain: career
entities: [companies/anthropic, people/jane-smith]
source: email-auto
email_id: <Gmail message ID>
email_from: jane-smith@anthropic.com
email_subject: 2차 면접 일정 확인
email_received_at: 2026-04-19T14:30:00+09:00
email_body_hash: {sha256}
---

## Summary
(LLM 요약)

## Original (link)
[Open in Gmail]({gmail_url})
```

---

## 4. MVP 상태

**해당사항 없음**. 요구사항만 정의. 구현은 v1.0.

---

## 5. 관련 FR (v1.0)

- **FR-A2** 구조화 기록 (email-note 템플릿)
- **FR-C1·G2** 엔티티 자동
- **FR-H2** 외부 읽기 (유사 패턴)
- **FR-G5** 논리 비약 (민감 메일 처리 주의)

---

## 6. v1.0 구현 단계 (참고)

- **v1.0 Week 1**: Gmail OAuth 설정 + IMAP/API 선택
- **v1.0 Week 1**: 필터 설정·테스트
- **v1.0 Week 2**: capture 통합 + entity-extract 연동
- **v1.0 Week 2**: 민감 필터 (재무 로컬만)
