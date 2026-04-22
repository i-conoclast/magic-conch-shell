# 05. External Task System 비교

**작성일**: 2026-04-19
**목적**: 확정 플랜의 영속 저장·외부 태스크 시스템 선택

---

## 요구사항 재확인

| FR | 선정 영향 |
|---|---|
| FR-H1 외부 태스크 쓰기 | API·SDK 지원 |
| FR-H2 기존 시스템 읽기 | 읽기 API도 필요 |
| FR-D5 확정 플랜 반영 | 구조화 필드 (도메인·마감일·우선순위) |
| NFR-07 유지보수성 | 기존 사용 중이면 제로 학습 비용 |

**중요 전제**:
- 사용자는 이미 **Notion**을 OKR·KR 트래커의 SSoT로 사용 중
- plan-tracker 프로젝트가 Notion DB 7종을 자동 집계
- 즉 **"새 도구 추가"가 아닌 "기존 Notion과 어떻게 연동할지"** 문제

이 조건 하에서는 Notion 대체는 **비합리적**. 하지만 사용자가 (b) 재검토 요청했으므로 후보 비교.

---

## 후보

### A. Notion (현재 사용 중)

**개요**: 데이터베이스·페이지 워크스페이스. 사용자의 기존 SSoT.

**장점**:
- ✅ **이미 사용 중** — 제로 학습·이전 비용
- ✅ plan-tracker의 7개 DB와 자동 연동
- ✅ OKR → KR → Daily Tasks → Activities 자동 집계 Rollup 이미 구축
- ✅ Python SDK (`notion-client`) 성숙
- ✅ 관계형 DB + 블록 편집 혼합 — 태스크 + 컨텍스트 동시 관리
- ✅ 모바일 앱 강력

**단점**:
- ⚠️ API rate limit (초당 3 req)
- ⚠️ Notion 자체가 외부 서비스 — 다운 시 영향 (FR-I3로 완화)
- ⚠️ Notion 변경 시 plan-tracker + magic-conch-shell 둘 다 영향

**추천도**: ⭐⭐⭐⭐⭐ — 기존 자산 활용

---

### B. Todoist

**개요**: 2026년 가장 인기 있는 개인 태스크 매니저. Gemini 2.5 Flash 기반 음성 입력 내장.

**2026년 최신**:
- **Todoist Ramble**: 음성 → 구조화 태스크 자동 변환
- 자연어 입력 강력 ("내일 오후 3시 미팅")
- 반복 태스크 우수

**장점**:
- ✅ 태스크 매니저 단일 목적 — Notion보다 가벼움
- ✅ API 성숙
- ✅ 자연어 입력 강력

**단점**:
- ❌ **OKR·KR 구조 없음** — plan-tracker의 Rollup 대체 불가
- ❌ 전환 비용 (기존 Notion DB 7종 마이그레이션)
- ❌ Notion과 Todoist 둘 다 쓰면 동기화 복잡

**추천도**: ⭐ — 전환 비용 > 이득

---

### C. Linear

**개요**: 엔지니어링·프로덕트 팀 전용 태스크 매니저.

**장점**:
- ✅ 엔지니어링 워크플로 강력 (이슈·사이클·프로젝트)
- ✅ 키보드 UX 최고
- ✅ API·GraphQL 성숙

**단점**:
- ❌ 팀 도구 — 개인 라이프 관리 부적합
- ❌ 건강·관계·재무 도메인 표현 어려움
- ❌ 비싸고 오버킬

**추천도**: ⭐ — 목적 불일치

---

### D. Obsidian + Dataview

**개요**: 로컬 마크다운 노트 + 쿼리 플러그인.

**장점**:
- ✅ 로컬 우선 (NFR-01 최강)
- ✅ 마크다운 — magic-conch-shell의 brain/과 같은 포맷
- ✅ 공개 표준

**단점**:
- ❌ **모바일 앱 약함** (아침 브리핑 iPhone 수신 불편)
- ❌ plan-tracker Rollup 대체 기능 부족
- ⚠️ 이미 사용 중인 Notion 데이터 이전 복잡

**추천도**: ⭐⭐ — 철학 부합하지만 실용성·전환 비용

---

### E. 자체 파일 시스템 (Notion 대체 없이)

**개요**: 확정 플랜을 brain/ 안 별도 폴더(plans/)에 저장하고 외부 시스템 연동 없이 완결.

**장점**:
- ✅ 최단 경로
- ✅ 의존성 제로

**단점**:
- ❌ plan-tracker의 KR Rollup 끊김 — OKR 진도 측정 불가
- ❌ 사용자의 기존 워크플로(Notion 대시보드 조회) 단절

**추천도**: ⭐ — 사용자 전체 시스템 붕괴

---

## 비교 요약

| 항목 | Notion | Todoist | Linear | Obsidian | 자체 |
|---|---|---|---|---|---|
| 사용자 현재 사용 | ✅ | ❌ | ❌ | ❌ | ❌ |
| OKR 구조 | ✅ | ❌ | ⚠️ | ⚠️ 플러그인 | 직접 |
| plan-tracker 연동 | ✅ 기본 | ❌ | ❌ | ⚠️ | ❌ |
| API 품질 | ✅ | ✅ | ✅ | ⚠️ | N/A |
| 모바일 | ✅ | ✅ | ⚠️ | ❌ | ❌ |
| 전환 비용 | 0 | ↑↑ | ↑↑ | ↑↑ | ↑↑↑ |
| 로컬 우선 (NFR-01) | ❌ | ❌ | ❌ | ✅ | ✅ |
| 학습 비용 | 0 | 중 | 중 | 중 | 높음 |

---

## 권장: **Notion (현재 사용 중인 것 유지)**

**선정 근거**:
1. **기존 Notion 워크스페이스와 plan-tracker 통합이 이미 작동 중** — 깨지 않음
2. **제로 전환 비용** — 다른 선택지는 시간 낭비
3. **OKR·KR·Daily Tasks Rollup 자동 집계가 이미 구축** — 새로 구현할 것 없음
4. **Python SDK (`notion-client`) 성숙** — 통합 쉬움
5. **모바일 앱으로 iPhone 조회 원활** — Step 2 사용 맥락 부합

**연동 구현 포인트**:
- `notion-client` Python SDK
- 쓰기: 확정 플랜 → `Daily Tasks` DB (plan-tracker 공유 스키마 준수)
- 읽기: 캘린더·오늘 예정·KR 현재값 조회
- API rate limit 대응: 로컬 큐 + backoff (FR-I3)

**계약**:
- magic-conch-shell이 쓰는 필드는 기존 plan-tracker 스키마 준수
- Source 필드에 `magic-conch-shell` 마킹으로 구분
- 기존 Daily Tasks에 없는 새 필드(예: brain/ 파일 경로)는 `Brain Ref` 속성으로 추가

---

## 위험 & 완화

| 위험 | 완화 |
|---|---|
| Notion API 장애 | 로컬 큐 + 재시도 (FR-I3 표준 대응) |
| Rate limit 초과 | 지수적 backoff + 배치 호출 |
| plan-tracker 스키마 변경 | 계약 문서화 + 버전 관리 |
| 이중 쓰기(사람+에이전트) 충돌 | Source 필드로 구분 + 상태 변경은 사용자·plan-tracker만 |

---

## 추가 고려: 캘린더

사용자가 "캘린더·태스크 시스템 읽기"를 MVP 외부 시그널로 선택 (Step 3).
캘린더 옵션:

- **Google Calendar** — 광범위하게 사용, API 성숙
- **Apple Calendar (iCal)** — Mac·iPhone 네이티브
- **Notion Calendar** — 기존 생태계 연장

**권장**: 사용자가 실제로 사용하는 것 확인 후 결정. 대부분 **Google Calendar**가 일반적. Apple Calendar는 로컬 파일(`~/Library/Calendars/`) 접근도 가능.

→ 이 결정은 **00-decisions.md에서 사용자 확인 후 확정**.

---

## 출처

- [12 Best Notion Alternatives 2026](https://blog.rivva.app/p/notion-alternatives-for-tasks)
- [Notion vs Todoist 2026](https://get-alfred.ai/blog/notion-vs-todoist)
- [Notion vs Todoist Business Dive](https://thebusinessdive.com/todoist-vs-notion)
- plan-tracker/docs/notion_db_v2.md (내부 참조, 기존 Notion DB 7종 스키마)
