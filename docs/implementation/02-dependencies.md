# 기능 의존성 그래프

**작성일**: 2026-04-22

MVP 41 FR 간의 의존 관계. 구현 순서 결정 근거.

---

## 1. 레이어별 의존 (하위 → 상위)

```
┌─────────────────────────────────────────────────────────┐
│  Layer 5: Planning Cycle (FR-D)                         │
│    D1 브리핑  D2 확정  D3 회고  D4 주간  D5 push         │
└────┬─────────────────────────┬──────────────────────────┘
     │                         │
     ▼                         ▼
┌─────────────────┐   ┌─────────────────────────┐
│  Layer 4: Agent │   │  Layer 4: Voice (F)     │
│    E1~E5        │   │    F1~F4                │
└────┬────────────┘   └────────┬────────────────┘
     │                         │
     └─────────┬───────────────┘
               ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Evolution (FR-G)                              │
│    G1 요약  G2 태깅  G3 인박스  G4 user-model  G5 챌린지 │
└─────────┬───────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: Entity + Integration (FR-C, FR-H)             │
│    C1~C5 entities   H1~H4 integration                   │
└────┬─────────────────────────┬──────────────────────────┘
     │                         │
     ▼                         ▼
┌──────────────────┐   ┌──────────────────────────┐
│  Layer 1:        │   │  Layer 1: Memory (FR-B)  │
│  Capture (FR-A)  │   │   B1~B5                  │
│   A1~A5          │   │                          │
└────────┬─────────┘   └────────┬─────────────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 0: Infrastructure                                │
│   - brain/ (SSoT)                                       │
│   - memsearch + Milvus Lite                             │
│   - Ollama 0.21 + MLX (via llm-server-template-ollama)  │
│   - Hermes Agent v0.10                                  │
│   - FastMCP (server·client)                             │
│   - Python 3.13.12 + uv                                 │
└─────────────────────────────────────────────────────────┘
                     ▲
                     │
┌─────────────────────────────────────────────────────────┐
│  Layer -1: Admin (FR-I) — cross-cutting                 │
│   I1 doctor  I2 reindex  I3 장애·큐                      │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 핵심 블로커

### Infrastructure (L0) → 모든 것
- Python/uv 없이 아무것도 못 함 (Day 0 완료)
- brain/ 디렉토리 없이 capture 못 함 (Day 1 스캐폴드)
- memsearch 없이 search 못 함 (Day 2 검증 필요)
- Hermes 없이 skill·agent 호출 못 함 (Day 0 완료)
- FastMCP 없이 mcs를 Hermes에 노출 못 함 (Week 2)

### Capture (FR-A) → Search·Entity·Planning
- A1 (캡처) 없으면 B1 (검색) 무의미
- A4 (파일 watcher) 는 A1 기반
- A5 (중복 감지) 는 .brain/state.json 필요

### Entity (FR-C) → Back-link·Timeline·Planning
- C1 (초안 생성) 은 A 캡처 후 entity-extract skill로
- C3 (back-link) 은 C1, A 완료 후
- C2 (승인) 은 D3 (evening-retro) 에 내장
- C5 (merge) 은 C4 (프로필) 기반

### Voice (FR-F) → Agent 응답
- F1 (톤 판단) 은 F2, F3, F4 전제
- F2·F3 는 LLM 호출 필요 (Layer 0)
- F4 (streak) 는 state.json 의존 (Layer 0)

### Evolution (FR-G) → Planning·UX
- G1 (세션 요약) 은 Hermes 세션 종료 이벤트 필요
- G2 (자동 태깅) 은 C1 기반
- G3 (인박스) 는 C2, E5 통합 지점
- G4 (user-model) 은 Week 3 이후 학습 데이터 필요
- G5 (챌린지) 은 F2 (컨설팅 톤) 기반

### Integration (FR-H) → Planning
- H1·H2 (Notion) 은 플래닝 루프의 외부 의존
- H3 (iMessage) 은 D1 브리핑 송수신
- H4 (이메일) 은 MVP 외

### Planning Cycle (FR-D) — 최종 레이어
- D1 (아침 브리핑) = **MVP 최소 승리**. 모든 하위 레이어 완성되어야 동작.
- D2 (플랜 확정) 은 D1 이후 대화
- D3 (저녁 회고) 은 C2, E5, G3 통합
- D4 (주간 리뷰) 은 H2 (Notion 읽기), plan-tracker MCP, 지난 주 daily
- D5 (Notion push) 은 H1 기반

---

## 3. 구현 순서 (의존성 기반)

```
Week 1: Layer 0 + Layer 1
  Day 1: L0 scaffold
  Day 2: L0 memsearch + embedding 검증 ⚠️
  Day 3-5: L1 capture (A1-A4) + search (B1, B2)
  Day 6-7: L1 entities 기초 (C1, C3) — skill 없이 tool로

Week 2: Layer 2 + agent runtime
  Day 1-2: Hermes skill symlink, MCP server 기초 (memory tools 노출)
  Day 3-4: conch-answer (F1-F3), entity-extract skill (C1/G2)
  Day 5: iMessage (H3) adapter 연결
  Day 6-7: B4 엔티티 타임라인 + B3 daily 뷰

Week 3: Layer 4+5 — Planning loop
  Day 1-2: morning-brief skill (D1) + LLM 라우팅
  Day 3: plan-confirm (D2) + Notion push (D5, H1)
  Day 4: evening-retro (D3) + approval inbox (G3) + entity confirm (C2)
  Day 5: plan-tracker MCP client (OKR read)
  Day 6-7: weekly-review (D4) + 튜닝

Week 4: Layer -1 + 안정화
  Day 1-2: mcs doctor (I1), reindex (I2), queue 관리 (I3)
  Day 3: Hermes cron 스케줄 등록
  Day 4-7: 실사용 + 튜닝 + streak 방지 (F4) + G4·G5
```

---

## 4. 병행 트랙

### Track A: 로컬 백엔드 (critical path)
- memsearch → capture → search → entity → planning
- 모든 날짜를 점유

### Track B: Hermes skill 문서·프롬프트 (병행 가능)
- Week 1 중: skills/*.md 프롬프트 초안 작성 (코드 대기 중)
- Week 2 시작 시 동기화

### Track C: plan-tracker MCP 서버 (별도 repo)
- 별도 repo 작업. Week 2 시작하여 Week 3 마감 전 완료.
- magic-conch-shell 쪽 tool wrapper는 graceful fallback이라 지연 OK.

### Track D: 사용자 데이터 이전·백업
- 기존 마크다운 메모 → `brain/` 참조 or 마이그레이션 (사용자 판단)
- restic 백업 스크립트 주 1회 cron

---

## 5. 블록된 기능 (critical path 외)

MVP 4주 내 **하지 않는** 기능 — 모든 의존성 만족해도 Week 4 이후:

- **FR-A2 음성 녹음** — 명시적 MVP 제외
- **FR-B5 관련도 세밀 튜닝** — 기본 memsearch RRF만
- **FR-C4 엔티티 병합 UI** — 수동 CLI 명령만
- **FR-E4 DIY workflow 추가** — 사용자 직접 .md 작성
- **FR-E5 자동 스킬 승격** — Hermes 내장 기능 활용 (우리 코드 X)
- **FR-G4 user-model 고도화** — 기본 파일만
- **FR-G5 논리 비약 챌린지** — Week 4 후반 튜닝
- **FR-H4 이메일 자동 수집** — v1.0
- **FR-D4 심화 주간 리뷰** — 간소 버전만

---

## 6. 데이터 플로우 의존 (런타임)

```
[사용자 입력 (iMessage · CLI · 파일)]
          │
          ▼
   [Hermes Agent]
          │
          ├─── [skill match] ─── conch-answer → 3-mode 라우팅
          │                         │
          │                         ├─── serious: agents/planner  
          │                         ├─── light: oracle-dictionary (no LLM)
          │                         └─── hybrid: memory.search + one-line
          │
          ▼
   [MCP tool call — stdio]
          │
          ▼
   [mcs (FastMCP server)]
          │
          ├── memory.search → memsearch → Milvus Lite + BGE-M3 embed
          ├── memory.capture → file.write → brain/{signals|domains}/...md
          ├── memory.entity_* → brain/entities/...
          ├── notion.* → notion-client → Notion API
          ├── llm.call → llm_router → Ollama (local) or Codex OAuth (remote)
          └── plan_tracker.* → plan-tracker MCP client → plan-tracker MCP server
```

**모든 런타임 경로는 MCP tool이 들어가 있어야 함** — Week 2 초에 최소 tool 구현 필수.

---

## 7. 실패 전파 (graceful degradation)

| 실패 지점 | 영향 | 대응 |
|---|---|---|
| Ollama 다운 | 오라클·엔티티 추출 중단 | Codex OAuth로 escalate (민감 데이터 제외) |
| Codex OAuth rate limit | 컨설팅 품질 낮음 | Ollama로 fallback |
| Notion 다운 | push 실패 | pending-push.jsonl 큐잉 |
| iMessage 실패 | 브리핑 전달 X | 터미널 출력 fallback |
| memsearch 손상 | 검색 먹통 | grep fallback + reindex 권장 |
| plan-tracker MCP 다운 | OKR 섹션 생략 | 브리핑·리뷰 축약 버전 |

---

## 8. 다음 문서

- [00-roadmap.md](00-roadmap.md)
- [01-day1-tasks.md](01-day1-tasks.md)
- [03-checkpoints.md](03-checkpoints.md)
