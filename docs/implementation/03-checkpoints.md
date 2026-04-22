# 검증 체크포인트

각 마일스톤에서 실행 가능한 **수동 체크**. 통과 못 하면 다음 단계 금지.

---

## 🔴 Day 2 End — Memory Engine 검증 (Critical Block)

**목적**: memsearch + BGE-M3가 한국어에서 쓸 만한지. 실패 시 전체 아키텍처 재검토.

### Test Setup
```bash
# brain/signals/ 에 한국어 샘플 10개 생성 (domains 다양)
cat > brain/signals/test-1.md <<'EOF'
---
id: test-1
type: signal
domain: career
created_at: 2026-04-22T10:00:00+09:00
source: manual
---
오늘 Anthropic ML Recruiter 미팅. Jane Smith가 포지션 설명.
기술 인터뷰는 LoRA·RAG 중심이라 함.
EOF
# ... 10개 도메인별 샘플 생성
```

### Checks
- [ ] `mcs reindex` 성공 (모든 파일 인덱싱, <30초)
- [ ] `mcs search "면접"` → test-1 포함, top 3 안에
- [ ] `mcs search "LoRA 구현"` → ML 관련 노트 반환
- [ ] `mcs search "Jane"` → Jane 언급 노트 상위
- [ ] 질의 latency p95 < 2초
- [ ] 관련도 정성 평가: 10개 쿼리 중 7개 이상 기대와 일치

### Fail 조건 & 전환
- 정확도 <7/10 → **sqlite-memory + ko-sbert** 로 전환 (추가 ~3시간)
- latency >5s → 임베딩 모델 축소 (multilingual-e5-base 등)
- memsearch 설치 실패 → FAISS + 자체 FTS 구현 (큰 비용, 최후의 수단)

---

## 🟢 Day 7 End — Week 1 완료

**테마**: 브레인 기반 동작

### Functional
- [ ] `mcs capture "한 줄"` → brain/signals/*.md 생성
- [ ] `mcs capture "..." --domain career` → brain/domains/career/...md
- [ ] `mcs capture "..." --entity people/jane-smith` → draft 생성 (미존재 시)
- [ ] `mcs ingest some.md` → 파일 이동 + 인덱싱
- [ ] `mcs search "쿼리"` → 관련도 순 10개 결과
- [ ] `mcs search --domain career "..."` → 도메인 필터
- [ ] `mcs search --entity people/jane-smith` → 엔티티 연결 기록
- [ ] `mcs entity show people/jane-smith` → 프로필 + back-link
- [ ] `mcs entity confirm entities/drafts/...md` → entities로 이동
- [ ] File watcher 동작: `brain/incoming/test.md` 생성 → 자동 분류

### Non-functional
- [ ] 모든 명령 p95 <2초 (검색 포함)
- [ ] 50건 capture 실사용 1일 — 이상 없음
- [ ] back-link auto 영역만 시스템이 수정 (수동 영역 보존)
- [ ] 타임존 KST 정확

### Data
- [ ] brain/ 구조 정리: daily/, domains/, entities/, signals/ 존재
- [ ] prontmatter 파싱 100% 성공 (파싱 실패 0건)
- [ ] .brain/state.json processed_hashes 누적

---

## 🟢 Day 14 End — Week 2 완료

**테마**: 에이전트 살아남

### Hermes integration
- [ ] `~/.hermes/config.yaml` skill 디렉토리에 `~/magic-conch-shell/skills` 등록
- [ ] `hermes skills list` 에 magic-conch-shell skills 출력
- [ ] `hermes chat -q "test"` → default 모델 응답 정상
- [ ] `hermes doctor` 모든 항목 ✅

### MCP server
- [ ] `mcp/mcs-server.py` stdio 실행
- [ ] FastMCP 3.x 노출 tools: memory.search, memory.capture, memory.entity_*
- [ ] Hermes가 mcs MCP server에 연결 (config.yaml mcp_servers)
- [ ] Hermes skill에서 MCP tool 호출 성공

### Skills
- [ ] `conch-answer.md` 로드됨
- [ ] 진지 질문 ("오늘 커밋 몇 번?") → 컨설팅 톤 (옵션+근거)
- [ ] 가벼운 질문 ("심심") → 오라클 한 줄
- [ ] 애매 질문 → 컨설팅 기본
- [ ] `entity-extract.md` 자동 발동 (캡처 후 LLM 호출)

### iMessage
- [ ] Mac mini iCloud 로그인 완료
- [ ] Hermes iMessage 필터 설정 (사용자 전화번호만)
- [ ] iPhone → 메시지 → Hermes 응답 수신 성공 (1 왕복)
- [ ] Mac mini → iMessage → iPhone 수신 확인

---

## 🟢 Day 21 End — Week 3 완료

**테마**: 핵심 루프 수동 완성

### morning-brief
- [ ] `/brief` 수동 호출 → 브리핑 생성 30초 이내
- [ ] 브리핑 내용에 다음 포함:
  - 오늘 우선순위 3 (OKR·KR 근거 인용)
  - 어제 놓친 것
  - 최근 변화
  - 캘린더 2건
  - 질문 한 줄
- [ ] 브리핑이 brain/daily/YYYY/MM/DD.md 🌅 섹션에 저장됨
- [ ] iMessage로 전송됨

### plan-confirm
- [ ] iMessage 답장 → plan-confirm skill 발동
- [ ] 3턴 대화에서 맥락 유지
- [ ] 신규 태스크 자동 KR 매칭 표시
- [ ] "확정" 명시 → Notion Daily Tasks에 Source=magic-conch 항목 생성
- [ ] brain/plans/YYYY-MM-DD-*.md 저장

### evening-retro
- [ ] `/retro` 수동 호출 → Phase 1~4 진행
- [ ] 오늘 KR 기여 집계 표시
- [ ] 승인 인박스: 엔티티 draft 승인 가능
- [ ] 🌙 섹션 brain/daily/.../DD.md 에 저장

### plan-tracker MCP
- [ ] plan-tracker MCP server 실행 가능 (별도 repo)
- [ ] mcs의 okr.snapshot_current() 호출 성공
- [ ] 7 도메인 OKR·KR 스냅샷 반환
- [ ] MCP server down 시 graceful degrade (브리핑의 OKR 섹션 생략)

### Non-functional
- [ ] LLM 라우팅: 진지 → Codex, 반복 → Ollama local, 오라클 → 사전
- [ ] 민감 도메인 (재무·관계·건강·멘탈) → Ollama 강제
- [ ] Notion API 실패 시 pending-push.jsonl 큐잉
- [ ] 전체 morning → confirm → retro 루프 총 지연 < 5분

---

## 🎯 Day 28 End — MVP 달성

**MVP 최소 승리 조건**: 아침 브리핑 하나가 진짜로 돔.

### Automation
- [ ] Hermes cron `0 7 * * *` → /brief 자동 실행
- [ ] `0 22 * * *` → /retro 자동 실행
- [ ] `0 20 * * 0` → /weekly 자동 실행 (간소)
- [ ] cron 실행 후 brain/daily/... 자동 기록

### Stability
- [ ] `mcs doctor` 모든 항목 ✅ 또는 경고 이유 명시
- [ ] `mcs queue list` 외부 push 큐 상태 확인 가능
- [ ] `mcs reindex` 성공 (전체 또는 부분)
- [ ] 24시간 무중단 동작 (watcher + cron 살아있음)

### Real usage
- [ ] 1주일 이상 실사용 (Week 4 의 7일)
- [ ] 하루 평균 10건+ capture 유지
- [ ] 아침 브리핑 실제 읽고 응답 5일+
- [ ] 엔티티 10개+ 승인됨
- [ ] 3-mode voice 정성 평가: 진지 질문에 컨설팅, 가벼움에 한 줄

### Subjective
- [ ] "이 자식 진짜 내를 알아" 느낌 ≥ 8/10
- [ ] 유지보수 시간 주 5시간 이내
- [ ] 기존 시스템 (plan-tracker · Notion) 충돌 0

### Known v1.0 items (not blocking MVP)
- FR-A2 음성 녹음
- FR-E5 자동 스킬 승격 (Hermes 내장 활용만)
- FR-G4 user-model 고도화
- FR-G5 논리 비약 챌린지
- FR-H4 이메일 자동 수집
- tutor-english·tutor-ml agent

---

## 🚨 중간 중단 기준

### Day 2 after memory 검증
→ memsearch 실패 → 전환 판단. 3시간 추가 수용 가능. 그 이상이면 Day 3~4로 이동.

### Day 7 after Week 1
→ 검색 품질 나쁨 or 엔티티 자동 감지 작동 X → Week 2 진입 보류, 기반 튜닝에 2~3일 추가.

### Day 14 after Week 2
→ Hermes 통합 불안정 or iMessage 실패 → Week 3 skip하고 Week 3-4 합쳐서 기반 강화.

### Day 21 after Week 3
→ morning-brief 생성 실패 or 품질 낮음 (정성 <6/10) → MVP 축소 — iMessage 대신 터미널로, Notion push 대신 파일 저장으로.

### Day 28
→ 위 일부 실패했어도 "아침 브리핑 수동 1건이라도 잘 돔" 이면 MVP 기본 통과.
→ 브리핑조차 안 되면 MVP 실패 → 원인 분석 후 Week 5+ 연장.

---

## 📊 검증 로그

각 Day 말 간단 기록:
```
### Day N — YYYY-MM-DD
Checks: X/Y 통과
주요 이슈: ...
내일 계획: ...
```

일지 형태로 `brain/implementation-log/` 에 저장 권장 (자기 추적용).
