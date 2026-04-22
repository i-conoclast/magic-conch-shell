# magic-conch-shell — MVP Implementation Roadmap

**작성일**: 2026-04-22
**목표**: 4주 안에 **"아침 브리핑 하나가 진짜로 돈다"** (Step 7 MVP 최소 승리)
**Critical path 보장 원칙**: 해당 기간 안에 morning-brief가 동작 가능한 상태로 수렴.

---

## 1. 주차별 마일스톤 (데모 가능한 산출물)

각 주말에 사용자가 **직접 손 놓고 확인 가능한** 결과물.

### End of Week 1 — "브레인 기반"
- ✅ `mcs capture "..."` 작동 → brain/ 저장
- ✅ `mcs search "..."` 결과 반환 (memsearch + BGE-M3)
- ✅ 엔티티 draft 워크플로 (자동 감지·수동 승인)
- ✅ 파일 watcher 자동 수집 (브레인 inbox)
- ✅ `mcs doctor` 최소 기능 (경로·의존 체크)
- **데모**: 하루 수동 사용 — 10건+ 캡처 + 몇 개 검색 + 엔티티 초안 확인

### End of Week 2 — "에이전트 살아남"
- ✅ Hermes가 magic-conch-shell skills 인식
- ✅ `conch-answer` skill → 3-mode 톤 라우팅 (컨설팅/오라클/하이브리드)
- ✅ `entity-extract` skill 자동 발동
- ✅ iMessage ↔ Hermes 양방향 송·수신 (필터링 포함)
- ✅ `mcs ask "..."` → Hermes 호출로 응답
- **데모**: iMessage로 질문 → 컨설팅 답변 수신. 오라클 모드 한 줄 답 확인.

### End of Week 3 — "핵심 루프 완성"
- ✅ `morning-brief` skill 수동 실행 (Notion/brain 컨텍스트 조립 + LLM 생성)
- ✅ `plan-confirm` skill (iMessage 대화로 플랜 확정)
- ✅ `evening-retro` skill (승인 인박스 + 회고)
- ✅ Notion Daily Tasks push (FR-D5)
- ✅ plan-tracker MCP client 연결 (OKR snapshot 읽기)
- **데모**: 아침 7시에 `/brief` 수동 실행 → iMessage 브리핑 수신 → 답장 → 플랜 확정 → Notion 반영 확인

### End of Week 4 — "MVP 완결 + 실사용"
- ✅ Hermes cron 자동 실행 (`0 7 * * *` → `/brief`, `0 22 * * *` → `/retro`)
- ✅ MCP 서버 (`mcp/mcs-server.py`) Hermes 연결
- ✅ `mcs doctor` 전 기능 (상태·로그·큐)
- ✅ 학습·상담 agent 최소 1개 (예: tutor-ml)
- ✅ `mcs reindex`·장애 큐 확인
- **데모** = **MVP 최소 승리 조건**: 사용자가 아침에 자동 브리핑 받고, 플랜 확정하고, 저녁에 회고·인박스 처리까지 **하루 한 사이클 자율 동작**.

---

## 2. Critical Path (최단 경로)

MVP 최소 승리(아침 브리핑)까지 **blocker-free sequence**.

```
Day 1  SCAFFOLD
  └─ pyproject.toml, 디렉토리, mcs CLI entry (첫 --help)

Day 2  MEMSEARCH CHECK ⚠️ 병목 가능
  └─ memsearch + Milvus Lite 설치
  └─ BGE-M3 한국어 검색 품질 실측 (10건 샘플)
  └─ 실패 시: sqlite-memory or multilingual-e5-large로 전환

Day 3-5  CAPTURE + SEARCH
  └─ mcs capture (text/file-watcher/CLI)
  └─ mcs search (자유 질의)
  └─ frontmatter 파싱·저장·인덱싱

Day 6-7  ENTITIES + DRAFTS
  └─ entity draft 워크플로
  └─ back-link 자동 생성

Week 2  HERMES SKILLS
  └─ ~/.hermes/skills/ symlink (config 추가)
  └─ conch-answer·entity-extract SKILL.md
  └─ MCP server stdio 첫 tool (memory.search)

Week 3  PLANNING LOOP
  └─ morning-brief skill (Notion read + brain + LLM)
  └─ iMessage 양방향
  └─ plan-confirm dialog → Notion push
  └─ evening-retro + approval inbox
  └─ plan-tracker MCP client

Week 4  AUTOMATION
  └─ Hermes cron schedules
  └─ 안정화 + doctor + 실사용
```

---

## 3. 병행 가능 트랙 (critical path 막지 않으면서)

| 트랙 | 기간 | 병행 대상 |
|---|---|---|
| **plan-tracker MCP 서버 개발** | Week 2 시작 | 별도 repo. Week 3 연결까지 여유. |
| **Skill·agent 문서화** | Week 1~2 | 코드 안 되면 마크다운만 작성 |
| **Hermes skill 튜닝 (프롬프트)** | Week 2~4 상시 | 품질 반복 개선 |
| **user-model.md 업데이트** | 전반 | 사용 중 학습 |
| **tutor-english/ml agents** | Week 3~4 | MVP 이후에도 OK |

---

## 4. 검증 체크포인트

### Day 2 End — 메모리 엔진 검증 ⚠️ 🔴 Critical Block
- [ ] memsearch 설치 성공
- [ ] Milvus Lite 동작
- [ ] BGE-M3 임베딩으로 한국어 10문장 인덱싱
- [ ] 한국어 쿼리로 관련 문서 반환 (정성 평가 ≥ 7/10)
- **실패 시**: 작업 중단 → alternative 전환 (sqlite-memory·multilingual-e5-large)

### Day 7 End (Week 1) — 브레인 기반 동작
- [ ] 50건 capture 테스트 (터미널·파일 watcher)
- [ ] 검색 p95 latency < 2초 (NFR-02)
- [ ] 엔티티 draft 3건 이상 자동 감지
- [ ] back-link 양방향 자동 생성

### Day 14 End (Week 2) — 에이전트 호출
- [ ] `hermes chat -q "..."` → Ollama 응답 + skill 자동 로드 감지
- [ ] iMessage 송신·수신 1 왕복 성공
- [ ] conch-answer 3 모드 구분 (진지/가벼움/애매)
- [ ] mcs MCP server stdio로 Hermes와 tool 호출

### Day 21 End (Week 3) — 핵심 루프 수동 실행
- [ ] `/brief` 수동 호출 → 유효한 브리핑 생성 (300자 내)
- [ ] iMessage로 브리핑 도착
- [ ] 3턴 대화로 플랜 확정 (추가·수정·확정)
- [ ] Notion DB3에 Source=magic-conch 태스크 3개 이상 생성
- [ ] plan-tracker MCP okr_snapshot_current 응답 정상 (or graceful fallback)

### Day 28 End (Week 4) — MVP 달성
- [ ] 아침 7시 자동 브리핑 수신 (cron)
- [ ] 10건/일 캡처 실사용
- [ ] 저녁 회고 대화 1회 완주
- [ ] 엔티티 10개 이상 승인됨
- [ ] 3-mode voice 응답 가벼운 질문에 1줄, 진지 질문에 선택지
- [ ] **"이 자식 진짜 내를 알아"** 정성 평가 ≥ 8/10

---

## 5. 실패 시 플랜 B (Contingency)

| 블록 | 트리거 | 대응 |
|---|---|---|
| memsearch 한국어 품질 | Day 2 검증 실패 | sqlite-memory + FTS5 + `ko-sbert` 임베딩 |
| FastMCP 3.x API 변경 | Day 8 경 | 공식 `mcp` SDK 저수준 API로 구현 |
| Codex OAuth rate limit | Week 2 경험 | Claude API 백업 provider (월 $7~) |
| Hermes v0.10.x 불안정 | Week 2~3 | v0.10.0 고정 + 업데이트 보류, 필요시 OpenClaw fork |
| iMessage 수신 지연/실패 | Week 3 | Poke Gate 또는 BlueBubbles로 교체 |
| plan-tracker MCP 미완성 | Week 3 | Notion 직접 읽기 (옵션 A) fallback, v1.0에서 MCP 전환 |

---

## 6. 시간 예산 (하루 기준)

**사용자 가정**: 하루 2~4시간 개발 가능 (정규 업무 외).

| 주차 | 코딩 시간 | 학습·설치·디버깅 | 실사용·튜닝 |
|---|---|---|---|
| 1 | 60% | 30% (memsearch·우리 신규 코드) | 10% |
| 2 | 50% | 30% (Hermes 스킬 패턴·MCP) | 20% |
| 3 | 40% | 20% | 40% (플래닝 루프 튜닝) |
| 4 | 20% | 10% | **70% (실사용 + 튜닝)** |

Week 4 실사용 비중이 가장 커야 MVP 검증 가능.

---

## 7. 우선순위 원칙

### 사수해야 할 것
- **Day 2 메모리 엔진 검증** — 모든 후속 작업의 기반
- **Week 3 end 수동 morning-brief** — MVP 핵심. 이게 안 되면 전체 실패.
- **타임존 KST 고정** — 일지·cron 일관성
- **brain/ 백업** (restic 주 1회 최소) — user data는 복구 불가

### 양보 가능
- 학습·상담 agent (tutor-*) — v1.0 미뤄도 OK
- 자동 스킬 승격 (FR-E5) — MVP엔 수동 DIY만
- FR-G5 논리 비약 챌린지 — Week 4 후반 튜닝
- 주간 리뷰 심화 — 단순 버전만 MVP

---

## 8. 다음 문서

- [01-day1-tasks.md](01-day1-tasks.md) — Day 1 구체 태스크
- [02-dependencies.md](02-dependencies.md) — 기능 의존 그래프
- [03-checkpoints.md](03-checkpoints.md) — 주차별 검증 체크리스트 (상세)

---

## 9. 원칙 재확인

1. **MVP 최소 승리 조건을 포기하지 않는다** (아침 브리핑)
2. **Day 2 memsearch 검증 실패 시 즉시 전환** — 감정적 sunk cost 배제
3. **실사용 시간 확보** — Week 4 실사용·튜닝이 가장 중요
4. **기존 시스템 (plan-tracker·Notion) 깨뜨리지 않음**
5. **brain/ 데이터는 신성** — 파일 삭제·이전 극히 조심
