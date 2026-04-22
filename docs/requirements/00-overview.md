# 00. Overview — 요구사항 정의서 개요

**작성일**: 2026-04-19
**상태**: 초안 (스펙 정의 Phase 완료)

---

## 한 장 요약

**magic-conch-shell**은 사용자의 라이프·커리어 맥락을 스스로 축적하는 **개인 메모리 + 에이전트 시스템**이다.

- **메모리**는 자유 메모·구조화 기록·엔티티(사람·회사·직무 등)를 3축으로 축적
- **에이전트**는 플래닝·회고·학습 세션·오라클 4가지 역할로 사용자와 상호작용
- 두 레이어는 서로 주고받으며 **시간이 갈수록 사용자 맥락을 깊이 이해**
- 가벼운 질문엔 소라고둥처럼 단호하게, 진지한 질문엔 선택지와 근거로 응답

---

## 누구를 위한 시스템인가

- **솔로 사용자 1명**: 커리어 전환 준비 중, 5개 라이프 영역(커리어·건강·멘탈·관계·재무)에 걸친 OKR 운영
- 기존에 **OKR 트래커·외부 태스크 시스템·마크다운 메모**를 쓰고 있음
- 기존 시스템과 **공존하며 빈 영역을 메우는** 역할

---

## 어떤 문제를 해결하는가

메타 문제:
> **시스템이 자기 관리 못함 → 사용자가 유지관리 노동에 시간을 뺏김 → 지속 어려움.**

세부 문제 5개 (P1~P5):
- P1 맥락 재공급 비용
- P2 상위 목표 수동 생성
- P3 외부 환경 변화 무반응
- P4 메모리 자동 축적 안 됨
- P5 반복 워크플로 구축 비용

→ 자세한 내용은 [01-background.md](01-background.md).

---

## 어떻게 해결하는가 (요구사항 요약)

### 입력·저장 (A·B·C)
- 터미널·채팅·파일 타이핑 3채널로 캡처 (A)
- 하루·타임라인·엔티티 기반 보기 (B)
- 사람·회사·직무·책을 1급 시민 엔티티로 (C)

### 상호작용 (D·E·F)
- 아침·저녁 정기 사이클 (D)
- 반복 워크플로 틀 제공 + DIY 추가 (E)
- 상황별 자동 톤 판단 (F)

### 진화·운영 (G·H·I)
- 메모리·에이전트 간 자동 주고받음 + 승인 인박스 (G)
- 외부 시스템과 읽기·쓰기 연동 (H)
- 상태 점검·장애 대응 (I)

→ 자세한 요구사항은 [03-functional/](03-functional/).

---

## 제약 요약

- **로컬 우선**: 민감 데이터는 로컬에서 처리. 외부 API는 품질 필요 시만
- **월 비용 $20 이하**
- **솔로 운영**: 2~3개월 초기 구현, 주 5시간 이하 유지
- **24/7 허브 가동**
- **한·영 혼용**

→ [05-constraints.md](05-constraints.md).

---

## 비기능 요구사항

- 캡처·검색 2초 이내, 브리핑·세션은 10~30초
- 외부 장애 시 로컬 큐 + 제한 기능 지속
- 데이터 이식성: 폴더 하나 복사로 다른 기기 복원
- 아첨·잔소리 금지, 단호함 + 유머 이중성 유지

→ [04-non-functional.md](04-non-functional.md).

---

## 성공 기준 (6개월 후)

1. 플래닝 들이는 시간이 줄어듦
2. "지난번 이야기" 반복 설명 줄어듦
3. 여러 워크플로가 로테이션으로 돌아감

**MVP 4주 최소 승리**: 아침 브리핑 하나가 진짜로 돔.

→ [06-success-criteria.md](06-success-criteria.md).

---

## 문서 내비게이션

| 파일 | 내용 |
|---|---|
| [00-overview.md](00-overview.md) | 이 파일 — 1 페이지 요약 |
| [01-background.md](01-background.md) | 문제 정의·가설 |
| [02-user-context.md](02-user-context.md) | 사용자 프로필·하루 타임라인·사용 맥락 |
| [03-functional/](03-functional/) | 9 카테고리 × 3분할 기능 요구사항 (27 파일) |
| [04-non-functional.md](04-non-functional.md) | 비기능 요구사항 |
| [05-constraints.md](05-constraints.md) | 제약 |
| [06-success-criteria.md](06-success-criteria.md) | 성공 기준 |

### 기능 요구사항 카테고리 (03-functional/)

| # | 카테고리 | 파일 |
|---|---|---|
| A | Capture (입력·캡처) | [fr](03-functional/A-capture-fr.md) · [criteria](03-functional/A-capture-criteria.md) · [scenarios](03-functional/A-capture-scenarios.md) |
| B | Memory (저장·검색) | [fr](03-functional/B-memory-fr.md) · [criteria](03-functional/B-memory-criteria.md) · [scenarios](03-functional/B-memory-scenarios.md) |
| C | Entities (1급 시민) | [fr](03-functional/C-entities-fr.md) · [criteria](03-functional/C-entities-criteria.md) · [scenarios](03-functional/C-entities-scenarios.md) |
| D | Planning (플래닝 사이클) | [fr](03-functional/D-planning-fr.md) · [criteria](03-functional/D-planning-criteria.md) · [scenarios](03-functional/D-planning-scenarios.md) |
| E | Sessions (학습·상담 워크플로) | [fr](03-functional/E-sessions-fr.md) · [criteria](03-functional/E-sessions-criteria.md) · [scenarios](03-functional/E-sessions-scenarios.md) |
| F | Voice & Tone (응답 스타일) | [fr](03-functional/F-voice-fr.md) · [criteria](03-functional/F-voice-criteria.md) · [scenarios](03-functional/F-voice-scenarios.md) |
| G | Evolution (상호작용·자동화) | [fr](03-functional/G-evolution-fr.md) · [criteria](03-functional/G-evolution-criteria.md) · [scenarios](03-functional/G-evolution-scenarios.md) |
| H | Integration (외부 시스템) | [fr](03-functional/H-integration-fr.md) · [criteria](03-functional/H-integration-criteria.md) · [scenarios](03-functional/H-integration-scenarios.md) |
| I | Admin (관리·장애 대응) | [fr](03-functional/I-admin-fr.md) · [criteria](03-functional/I-admin-criteria.md) · [scenarios](03-functional/I-admin-scenarios.md) |

---

## 다음 Phase

- **[features/](../features/)**: 기능 목록·우선순위·FR 추적표
- **design/** (추후): 기술 선택·아키텍처 — 아직 없음
- **implementation/** (추후): 코드 — 아직 없음

---

## 원칙 재확인

이 요구사항 정의서에는 **구체 기술·제품명이 등장하지 않는다.** Hermes·memsearch·Notion·Python 등은 `design/` 단계에서 선택·등장.
