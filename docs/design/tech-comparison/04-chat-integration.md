# 04. Chat Integration 비교

**작성일**: 2026-04-19
**목적**: iMessage·채팅 채널을 통한 양방향 통신 구현 방식 선택

---

## 요구사항 재확인

| FR / NFR | 선정 영향 |
|---|---|
| FR-H3 채팅 양방향 | 송·수신 둘 다 필수 |
| FR-D1 아침 브리핑 | 스케줄 기반 send 필수 |
| FR-D2 플랜 확정 대화 | 3턴 이상 양방향 맥락 유지 |
| NFR-04 신뢰성 | 장애 시 fallback 필요 |
| NFR-07 유지보수성 | 솔로 운영 가능한 복잡도 |

**사용자 전제**: iPhone 주 사용. iMessage가 기본 채널.

---

## 후보

### A. Hermes Agent 내장 iMessage 지원

**개요**: Hermes Agent가 이미 14 플랫폼 채팅 지원. iMessage 포함.

**장점**:
- ✅ **가장 간단** — Hermes 설정만으로 양방향 구현 (설정 1장)
- ✅ Hermes 메모리·스킬과 자연 통합
- ✅ 다른 플랫폼(Telegram 등) 추가도 설정 변경만으로 가능
- ✅ 유지보수 주체가 Hermes — NFR-07 부담 최저

**단점**:
- ⚠️ Hermes가 iMessage 구현 어떻게 하는지 내부 확인 필요 (AppleScript? BlueBubbles?)
- ⚠️ Hermes v0.x 의존 — 변경 리스크

**추천도**: ⭐⭐⭐⭐⭐ — Hermes 선택시 최우선 고려

---

### B. Poke Gate

**개요**: iMessage·Telegram·SMS를 MCP 터널로 Mac에 연결. MIT 라이선스.

**특징**:
- **MCP 기반**: 에이전트 도구로 통합
- **Push 방식**: Mac이 스케줄대로 메시지 발송 (agents 폴더에 JS)
- **오픈소스**

**장점**:
- ✅ iMessage 외 다른 채널도 커버
- ✅ MCP 표준 — 다른 에이전트와 호환

**단점**:
- ⚠️ Hermes 내장 대비 추가 구성요소
- ⚠️ JavaScript 기반 agents — 우리 Python 스택과 이중화

**추천도**: ⭐⭐⭐ — Hermes 내장이 안 되면 후보

---

### C. imessage-mcp-server

**개요**: AppleScript로 iMessage 송신·연락처 관리하는 MCP 서버.

**장점**:
- ✅ 경량 (단일 기능)
- ✅ MCP 표준
- ✅ AppleScript 기반 — Mac 네이티브

**단점**:
- ❌ **수신 처리 부족** — AppleScript로 수신 주기 polling 방식은 비효율
- ⚠️ 연락처 관리까지만 — 풍부한 대화 기능 부족

**추천도**: ⭐⭐ — 송신 전용이면 OK, 양방향엔 약함

---

### D. macos-automator-mcp

**개요**: AppleScript·JXA 실행 MCP 서버. 200+ 프리셋 자동화 포함.

**장점**:
- ✅ 광범위한 Mac 자동화 (iMessage 포함)
- ✅ 커스텀 스크립트 실행

**단점**:
- ❌ iMessage 특화 아님 — 범용 자동화
- ❌ 양방향 대화 맥락 관리 직접 구현 필요

**추천도**: ⭐⭐ — 범용성 좋으나 전용 도구가 유리

---

### E. macOS26/Agent 네이티브 앱

**개요**: 17 LLM 공급자 지원 네이티브 Mac 앱. iPhone에서 Messages로 태스크 실행.

**장점**:
- ✅ 완성도 높은 네이티브 앱
- ✅ AppleScript 50 앱 자동화
- ✅ MCP 확장

**단점**:
- ❌ **앱 UI 중심** — CLI·Hermes 통합 복잡
- ❌ 우리는 헤드리스(headless) 허브 필요, 앱 아님
- ⚠️ MIT인지 확인 필요

**추천도**: ⭐⭐ — 별개 제품, 우리 아키텍처와 불일치

---

### F. BlueBubbles + 자체 REST 클라이언트

**개요**: iMessage를 REST API로 접근하는 오픈소스 서버.

**장점**:
- ✅ 표준 HTTP — 어디서나 호출
- ✅ 양방향 지원 견고 (webhook)
- ✅ 성숙한 프로젝트

**단점**:
- ⚠️ BlueBubbles 서버 별도 실행 필요 (관리 부담)
- ⚠️ 설정 복잡 (iCloud 인증 등)

**추천도**: ⭐⭐⭐ — Hermes·Poke Gate 불가 시 견고한 대안

---

## 비교 요약

| 항목 | Hermes 내장 | Poke Gate | imessage-mcp | automator-mcp | macOS26 Agent | BlueBubbles |
|---|---|---|---|---|---|---|
| 양방향 (FR-H3) | ✅ | ✅ | ⚠️ polling | ⚠️ | ✅ | ✅ |
| 수신 webhook | ✅ 내부 처리 | ✅ | ❌ | ❌ | ✅ | ✅ |
| 다중 채널 | ✅ 14개 | ✅ 3개 | ❌ iMessage only | ⚠️ | ⚠️ | ❌ |
| MVP 4주 구현 난이도 | ✅ 최저 | ⚠️ 중 | ✅ 낮 (송신만) | ⚠️ | ❌ 높음 | ⚠️ 중 |
| Hermes 통합 | ✅ 네이티브 | ⚠️ MCP 중계 | ⚠️ MCP | ⚠️ MCP | ❌ | 직접 |
| 유지 부담 (NFR-07) | ✅ 최저 | ⚠️ | ✅ | ⚠️ | ❌ | ❌ 높음 |

---

## 권장: **Hermes Agent 내장 iMessage 지원**

**선정 근거**:
1. **01-agent-framework.md에서 Hermes 선택** → 내장 기능 우선 활용
2. **MVP 4주 부담 최소화** — 별도 구성요소 관리 X
3. **Hermes 메모리·스킬과 자연 통합** — 플랜 확정 대화 맥락이 그대로 스킬 메모리로
4. **14 플랫폼 확장성** — 미래에 Telegram·Slack 추가 쉬움

**구체 작업**:
- Hermes 설정 파일에 iMessage 플랫폼 활성
- Mac mini에 iCloud 계정 로그인 (iMessage 수신 위해)
- Hermes 전용 스킬로 아침 브리핑·플랜 확정 흐름 정의

---

## 위험 & 완화

| 위험 | 완화 |
|---|---|
| Hermes iMessage 구현 안정성 | Week 1에 양방향 테스트 필수. 실패 시 Poke Gate로 전환. |
| iCloud 계정 이중 로그인 | Mac mini 전용 계정 구성 (iPhone과 분리 고려) |
| iMessage 장애 (Apple 측) | 터미널 출력·로컬 알림 fallback (FR-I3) |
| Hermes 변경으로 채팅 연동 깨짐 | 추상 계층 구현 — Hermes API 래핑 |

---

## 대안 시나리오

Hermes 내장 iMessage가 안정적이지 않으면:

**플랜 B**: **Poke Gate + Hermes (MCP 통신)**
- Poke Gate가 iMessage 수·발신 담당
- Hermes가 MCP 클라이언트로 Poke Gate 도구 호출
- 복잡도 증가하지만 독립성 확보

**플랜 C**: **BlueBubbles + 얇은 Python 래퍼**
- 모든 채팅 의존성 제거
- REST·webhook 직접 다룸
- 유지 부담 ↑, 안정성 ↑↑

---

## 출처

- [Hermes Agent 14 Platforms](https://hermes-agent.nousresearch.com/)
- [Poke Gate — iMessage Remote Mac Control](https://www.buildmvpfast.com/blog/poke-gate-remote-mac-control-imessage-ai-agent-2026)
- [imessage-mcp-server](https://github.com/marissamarym/imessage-mcp-server)
- [macos-automator-mcp](https://github.com/steipete/macos-automator-mcp)
- [macOS26/Agent](https://github.com/macOS26/Agent)
- [iMessage API Revolution 2026](https://medium.com/@dwoank6ulo/mastering-the-imessage-api-a-comprehensive-guide-to-integrating-ai-with-apple-s-messaging-30c641c0cd23)
