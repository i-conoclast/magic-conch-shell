# 02. Memory Engine 비교

**작성일**: 2026-04-19
**목적**: magic-conch-shell의 메모리 저장·인덱싱·검색 엔진 선택

---

## 요구사항 재확인

| FR | 선정 영향 |
|---|---|
| FR-A1~A5 캡처 | 파일 기반 저장이어야 입력 채널 3종 통합 쉬움 |
| FR-B1 자유 질의 검색 | 의미 + 키워드 하이브리드 필요 |
| FR-B2 도메인·엔티티 필터 | 메타데이터 필터링 필수 |
| FR-B4 엔티티 타임라인 | 시간순 + 엔티티 연결 기반 쿼리 |
| FR-B5 관련도 정렬 | RRF·의미 유사성 지원 |
| FR-C3 back-link | 양방향 참조 관리 |
| FR-G2 자동 엔티티 태깅 | 본문에서 엔티티 탐지 |
| NFR-01 프라이버시 | 로컬 저장 우선 |
| NFR-05 이식성 | 폴더 복사로 이전 가능 |

**핵심 원칙**: "Markdown is the source of truth" (3 Beliefs)

---

## 후보 메모리 엔진

### A. memsearch (Zilliz)

**개요**: OpenClaw 메모리 시스템에서 추출된 독립 라이브러리. Markdown-first + Milvus 벡터 인덱스.

**특징**:
- **마크다운 = SSoT**: `.md` 파일이 원본, 벡터 DB는 재빌드 가능한 그림자 인덱스
- **하이브리드 검색**: dense vector + BM25 + RRF reranking
- **Live sync**: 파일 변경 실시간 감지·재인덱싱
- **SHA-256 해시 기반 중복 감지**
- **표준 Markdown — vendor lock-in 없음**

**장점**:
- ✅ 우리 철학과 완벽 일치 (Markdown SSoT)
- ✅ FR-A5 (중복 감지), FR-B5 (관련도) 기본 지원
- ✅ 파일 watcher 내장 (FR-A4)
- ✅ Milvus Lite로 로컬 완결 (NFR-01 부합)
- ✅ Python SDK — Hermes·Python 에이전트와 자연스러운 통합

**단점**:
- ⚠️ 벡터 인덱스로 Milvus 사용 — 메모리 사용량 큼
- ⚠️ 한국어 검색 품질 미확인 (임베딩 모델 의존)
- ⚠️ back-link·엔티티 연결은 직접 구현 필요 (검색까지만)

**추천도**: ⭐⭐⭐⭐⭐ — 핵심 철학 일치, 검색 품질 최상

---

### B. sqlite-memory (SQLiteAI)

**개요**: SQLite 확장으로 구현된 에이전트 메모리. 마크다운 청킹 + FTS5 + 벡터.

**특징**:
- **SQLite 확장**: 의존성 최소, 단일 파일 DB
- **하이브리드 검색**: FTS5 (전문 검색) + vector similarity
- **마크다운 인식 청킹**
- **오프라인 우선 + 에이전트 간 동기화**

**장점**:
- ✅ 경량 (SQLite 단일 파일)
- ✅ 백업·이식성 최상 (NFR-05)
- ✅ Milvus 대비 메모리·디스크 절약
- ✅ 표준 SQL 쿼리 가능

**단점**:
- ⚠️ FTS5는 한국어 형태소 분석 약함
- ⚠️ memsearch보다 생태계·성숙도 낮음
- ⚠️ Live sync 기본 X — 직접 구현

**추천도**: ⭐⭐⭐⭐ — 경량·이식성 원하면 최선

---

### C. Mem0

**개요**: 에이전트 전용 장기 메모리 레이어. 세션 간 영속성.

**특징**:
- **에이전트 메모리 전용**: 유저별·세션별 메모리 구조
- **자동 정제**: 중복 제거·요약
- **REST API + Python SDK**

**장점**:
- ✅ 에이전트 워크플로와 자연 통합
- ✅ 자동 중복·요약 기능

**단점**:
- ❌ 마크다운 우선이 아님 (DB 중심)
- ❌ 3 Beliefs 위반: SSoT가 DB
- ❌ 이식성 낮음 (폴더 복사 X, DB 마이그레이션 필요)

**추천도**: ⭐⭐ — 우리 철학과 불일치

---

### D. GBrain 스타일 직접 구현

**개요**: PGLite (임베디드 Postgres) + pgvector + pg_trgm. 이전 repo에서 사용.

**특징**:
- Postgres 기능 완전 활용 (JOIN·transaction·복잡 쿼리)
- pgvector로 벡터 검색
- 자체 스키마 자유도 최대

**장점**:
- ✅ SQL의 풍부한 기능
- ✅ 엔티티 연결·back-link 구현 자유로움

**단점**:
- ❌ Postgres 운영 부담 (NFR-07 위반)
- ❌ 4주 MVP 내 전체 쿼리 레이어 구현 부담
- ❌ 이식성 복잡 (DB dump·restore 필요)

**추천도**: ⭐⭐ — 오버엔지니어링

---

### E. 직접 벡터 검색 (raw FAISS·Chroma)

**개요**: 검색 라이브러리만 사용하고 나머지는 직접.

**장점**:
- ✅ 경량
- ✅ 커스터마이즈 자유

**단점**:
- ❌ 모든 기능 직접 구현 (watcher·하이브리드·중복 등)
- ❌ MVP 범위 초과

**추천도**: ⭐ — 4주 MVP에 부적합

---

## 비교 요약

| 항목 | memsearch | sqlite-memory | Mem0 | GBrain 스타일 | 직접 |
|---|---|---|---|---|---|
| Markdown SSoT (철학) | ✅ | ✅ | ❌ | ⚠️ | N/A |
| 하이브리드 검색 (FR-B5) | ✅ | ✅ | ⚠️ | 직접 | 직접 |
| 파일 watcher (FR-A4) | ✅ 내장 | ❌ | ❌ | 직접 | 직접 |
| 중복 감지 (FR-A5) | ✅ 내장 | ⚠️ | ✅ | 직접 | 직접 |
| 한국어 품질 | ⚠️ 임베딩 의존 | ⚠️ FTS 약함 | ⚠️ | 직접 | 직접 |
| 이식성 (NFR-05) | ✅ 파일+DB 분리 | ✅ 단일 파일 | ❌ | ⚠️ | ⚠️ |
| 메모리·디스크 | ⚠️ 큼 (Milvus) | ✅ 경량 | ⚠️ | ❌ 큼 | ✅ |
| MVP 4주 실현 | ✅ | ✅ | ⚠️ | ❌ | ❌ |
| back-link·엔티티 | 직접 구현 | 직접 구현 | 직접 구현 | SQL 자유 | 직접 |

---

## 권장: **memsearch (Zilliz) — 단, Milvus Lite 모드로 경량화**

**선정 근거**:
1. **3 Beliefs 중 Markdown SSoT 원칙 직접 구현** — 파일이 원본, 인덱스는 재빌드
2. **FR-A4·A5·B5 기본 내장** — 우리가 다시 구현할 필요 없음
3. **Hermes Agent + Python + memsearch** 조합은 2026년 현재 실증된 스택
4. **검색 품질 최상** (하이브리드 + RRF)

**선택 구성**:
- **Milvus Lite 로컬 모드** (Milvus 서버 X, 단일 프로세스 내장) — 메모리 경량화
- 임베딩: 로컬 모델(예: 다국어) + 한국어 튜닝 여지

**위험 인식**:
- 한국어 검색 품질 → MVP Week 1에 검증 테스트 필수. 떨어지면 sqlite-memory 플랜 B.
- Milvus 의존성 무거움 → Milvus Lite로 mitigate, 필요 시 sqlite-memory로 마이그레이션 계획

**직접 구현 보완**:
memsearch가 커버 안 하는 부분은 얇은 파이썬 레이어로:
- 엔티티 back-link 로직
- 엔티티 초안·승인 워크플로
- 도메인·엔티티 필터 쿼리 래핑

**대안 시나리오**:
- 한국어 검색 품질이 낮으면 → **sqlite-memory로 전환**. 마크다운 SSoT는 동일하게 유지되므로 데이터 손실 없음.

---

## 출처

- [memsearch — Zilliz/Milvus](https://github.com/zilliztech/memsearch)
- [We Extracted OpenClaw Memory System](https://milvus.io/blog/we-extracted-openclaws-memory-system-and-opensourced-it-memsearch.md)
- [sqlite-memory](https://github.com/sqliteai/sqlite-memory)
- [Top 6 AI Agent Memory Frameworks 2026](https://dev.to/nebulagg/top-6-ai-agent-memory-frameworks-for-devs-2026-1fef)
- [Markdown Memory Management](https://dev.to/imaginex/ai-agent-memory-management-when-markdown-files-are-all-you-need-5ekk)
