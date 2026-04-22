# 01. Agent Framework 비교

**작성일**: 2026-04-19
**목적**: magic-conch-shell의 에이전트 런타임·스킬 시스템·워크플로 엔진 선택

---

## 요구사항 재확인 (Requirements → 선정 기준)

| FR | 선정 영향 |
|---|---|
| FR-E1 워크플로 = 마크다운 1파일 | 스킬이 마크다운으로 정의되어야 함 |
| FR-E2 명시적 + 자동 트리거 | 자연어 트리거 지원 필요 |
| FR-E3 세션 진도 승계 | 세션 상태 영속화 메커니즘 |
| FR-E4 DIY 추가 | 재시작 없이 새 스킬 즉시 활성 |
| FR-E5 자동 스킬 승격 | 런타임이 스킬 자동 생성·편집 가능해야 |
| FR-G1/G2 세션 요약·태깅 자동화 | 에이전트 루프가 메모리에 write |
| FR-H3 채팅 양방향 | 채팅 플랫폼 연동 필수 |
| NFR-06 톤 (3 Beliefs) | 프롬프트·스킬 커스터마이즈 자유도 |
| NFR-07 유지보수성 | 솔로 운영 가능한 복잡도 |

---

## 후보 프레임워크

### A. Hermes Agent (Nous Research)

**개요**: 자기개선 기반 AI 에이전트. 2026년 2월 출시 후 33K+ GitHub stars.

**특징**:
- **Markdown skills**: `~/.hermes/skills/*.md` — 스킬이 마크다운 파일
- **3-layer memory**: skill / conversational / user modeling
- **자기 개선**: 복잡한 작업 후 자동으로 스킬 생성·편집
- **14 채팅 플랫폼 지원**: iMessage·Telegram·Discord·Slack·WhatsApp·Signal 등
- **LLM 무관**: Claude·OpenAI·Ollama·Qwen·OpenRouter 등 교체 가능
- **MIT 라이선스, 자체 호스팅**

**장점**:
- ✅ FR-E1~E5 직접 충족 (스킬 = 마크다운, 자동 승격 기본 기능)
- ✅ FR-G1·G2 직접 충족 (메모리 자동 저장·개선)
- ✅ 14 플랫폼 채팅 이미 지원 (FR-H3 용이)
- ✅ 자체 호스팅 — NFR 프라이버시 부합
- ✅ 2026년 현재 가장 활발한 개발 (v0.7.0+)

**단점**:
- ⚠️ 신생 프로젝트 (2026-02 출시) — API 안정성 불확실
- ⚠️ 자기 개선 로직이 블랙박스스러움 (추적 어려움)
- ⚠️ 2026-04 기준 프로덕션 사례 적음

**추천도**: ⭐⭐⭐⭐⭐ — 요구사항 7/9 직접 충족

---

### B. LangGraph (LangChain)

**개요**: LangChain 생태계의 스테이트풀 에이전트 프레임워크. 24.8K+ GitHub stars, 2024년 출시.

**특징**:
- **그래프 기반 에이전트**: 상태를 노드 간 전이로 모델링
- **세밀한 제어**: 단계별 개입·디버깅 가능
- **LangChain 통합**: 풍부한 툴·LLM·메모리 생태계
- **월 3450만 다운로드** (성숙도 최고)

**장점**:
- ✅ 안정성·성숙도 (Hermes 대비 2년 먼저 출시)
- ✅ 세밀한 워크플로 제어 (FR-E3 진도 승계에 유리)
- ✅ 프로덕션 사례 많음

**단점**:
- ❌ 스킬을 마크다운으로 정의하지 않음 — 파이썬 코드로 노드 작성 (FR-E1 위반)
- ❌ 자기 개선 기본 기능 없음 — FR-E5 직접 구현 필요
- ❌ 채팅 플랫폼 통합은 별도 구현 (FR-H3 부담)
- ⚠️ LangChain 추상화 레이어 복잡도 (NFR-07 솔로 운영 부담)

**추천도**: ⭐⭐⭐ — 안정적이나 요구사항과 철학이 다름

---

### C. OpenClaw

**개요**: 게이트웨이 기반 개인 AI 어시스턴트. SOUL.md 중심 인격 정의.

**특징**:
- **SOUL.md**: 에이전트 인격·가치관을 마크다운으로 정의
- **MEMORY.md + 일일 로그**: 평문 마크다운 메모리
- **BM25 + 벡터 하이브리드 검색**: 내장
- **게이트웨이 아키텍처**: 여러 LLM·플랫폼 라우팅

**장점**:
- ✅ 마크다운 우선 설계 (FR-E1 부합)
- ✅ 메모리 아키텍처 참조 가치 높음
- ✅ Hermes보다 먼저 나온 성숙한 시스템

**단점**:
- ⚠️ 자기 개선 기능 상대적 약함 (FR-E5 부족)
- ⚠️ 세션 진도 승계가 명시적 기능이 아님 (FR-E3 구현 부담)
- ⚠️ Hermes보다 활동성 낮아짐 (Hermes가 그 위에 구축됨)

**추천도**: ⭐⭐⭐ — 메모리·인격 참조는 좋지만 Hermes에 흡수됨

---

### D. OpenHarness (HKUDS)

**개요**: 홍콩대 연구그룹이 만든 CLI-first 에이전트 런타임. 인스펙터블·포크 중심.

**특징**:
- **harness + skills + tools** 3계층 명시 분리
- **Anthropic skills 호환** (마크다운)
- **루프 자체를 포크·개조** 가능
- **연구자·빌더 대상**

**장점**:
- ✅ 완전 투명성 — 모든 단계 인스펙트 가능
- ✅ Anthropic skills 호환 (마크다운, FR-E1)
- ✅ 포크해서 magic-conch 전용 루프 만들 수 있음

**단점**:
- ❌ MVP 4주에 부담 (진입 장벽 높음)
- ❌ 자기 개선·메모리 자동화는 직접 구현 필요
- ❌ 채팅 통합 부재

**추천도**: ⭐⭐ — v2.0+에서 Hermes 대체 고려 시 후보

---

### E. 자체 에이전트 루프 (Custom)

**개요**: LLM API 직접 호출 + 메모리·스킬 시스템 스스로 구현.

**장점**:
- ✅ 완전한 제어
- ✅ 불필요한 종속성 없음

**단점**:
- ❌ 4주 MVP 내 자기 개선·멀티 채팅·스킬 승격 구현 불가
- ❌ 솔로 운영 부담 폭증 (NFR-07 위반)

**추천도**: ⭐ — MVP 이후 v2.0 재검토 대상

---

## 비교 요약

| 항목 | Hermes | LangGraph | OpenClaw | OpenHarness | Custom |
|---|---|---|---|---|---|
| 마크다운 스킬 (FR-E1) | ✅ 기본 | ❌ | ✅ | ✅ | 직접 구현 |
| 자기 개선 (FR-E5) | ✅ 기본 | ❌ | ⚠️ | ❌ | 직접 구현 |
| 진도 승계 (FR-E3) | ✅ 기본 | ✅ 강력 | ⚠️ | ⚠️ | 직접 구현 |
| DIY 파일 추가 (FR-E4) | ✅ 즉시 | ❌ 재시작 | ✅ | ✅ | 직접 구현 |
| 채팅 통합 (FR-H3) | ✅ 14 플랫폼 | ❌ 별도 | ⚠️ | ❌ | 직접 구현 |
| 자동 메모리 (FR-G1) | ✅ 기본 | ⚠️ 직접 | ✅ | ❌ | 직접 구현 |
| 성숙도 | ⚠️ 신생 | ✅ 최고 | ✅ 안정 | ⚠️ 연구용 | N/A |
| 4주 MVP 실현성 | ✅ 높음 | ⚠️ 중간 | ✅ 높음 | ❌ 낮음 | ❌ 낮음 |
| NFR-07 유지보수 | ✅ | ⚠️ | ✅ | ⚠️ | ❌ |

---

## 권장: **Hermes Agent**

**선정 근거**:
1. **FR 직접 충족률 최고**: E1~E5 + G1·G2 + H3을 기본 기능으로 커버
2. **4주 MVP 실현 가능**: 핵심 기능이 이미 구현되어 있어 우리가 FR 7개를 다시 만들 필요 없음
3. **요구사항의 핵심 가설(자기 개선 워크플로 찍어내기)이 이 프로젝트의 중심 설계 철학**과 정렬
4. **14 플랫폼 채팅 통합**으로 iMessage 연동도 추가 구현 부담 적음
5. **MIT·자체 호스팅**으로 NFR 프라이버시 부합

**위험 인식**:
- v0.7.x 신생 — API 변경 가능성. 대응: 내부 추상 계층 1장 두고 교체 가능하게
- 자기 개선 로직 블랙박스 — 대응: 자동 승격 시 승인 필수(FR-E5)로 통제

**대안 시나리오**:
- Hermes가 블로커가 되면 **OpenClaw + 자체 구현 레이어**로 전환 (SOUL.md·하이브리드 검색 유지, 자기 개선만 자체 구현)

---

## 출처

- [Hermes Agent — Nous Research](https://github.com/nousresearch/hermes-agent)
- [Hermes Agent 2026 개요](https://www.ai.cc/blogs/hermes-agent-2026-self-improving-open-source-ai-agent-vs-openclaw-guide/)
- [Self-Improving AI Agent Deep Dive](https://dev.to/marwane_manifi_c4dacfeb34/hermes-agent-the-self-improving-ai-agent-that-runs-247-on-your-own-server-a-deep-dive-554p)
- [OpenClaw vs Hermes 비교](https://cognio.so/resources/guides/openclaw-vs-hermes)
- [Best Open Source Agent Frameworks](https://www.firecrawl.dev/blog/best-open-source-agent-frameworks)
- [Top 5 Open-Source Agentic AI Frameworks](https://aimultiple.com/agentic-frameworks)
