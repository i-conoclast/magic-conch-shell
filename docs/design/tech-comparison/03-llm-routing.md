# 03. LLM Routing 비교

**작성일**: 2026-04-19
**목적**: 로컬·클라우드 LLM 라우팅 전략 — 작업별 모델 선택

---

## 요구사항 재확인

| FR / NFR | 선정 영향 |
|---|---|
| NFR-01 프라이버시 | 민감 데이터 로컬 처리 |
| NFR-02 지연 | 캡처·조회 2초, 브리핑 10~30초 |
| NFR-08 비용 | 월 $20 상한 |
| FR-F1~F4 톤 판단 | 진지 질문에 품질 높은 응답 |
| FR-G5 논리 비약 지적 | 긴 맥락 추론 가능한 모델 |

---

## 두 축의 결정

1. **로컬 추론 엔진** (Mac mini 24/7): MLX / Ollama / llama.cpp / vLLM
2. **외부 LLM 라우팅** (품질 필요 작업): Claude API / OpenAI (Codex) / OpenRouter

---

## Part 1: 로컬 추론 엔진

### A. MLX (Apple)

**개요**: Apple 공식 ML 프레임워크. Metal 기반, Apple Silicon 최적화.

**벤치마크 (2026년 4월 기준)**:
- 14B 이하 모델에서 llama.cpp 대비 **20~87% 빠름**
- 7B 최적화 모델에서 **230 tokens/sec** (5~7ms latency)
- 27B+에서는 메모리 대역폭 포화로 llama.cpp와 비슷

**장점**:
- ✅ Apple Silicon에서 가장 빠름 (<14B)
- ✅ Metal 직접 활용 — 에너지 효율
- ✅ mlx-community에 최신 모델 빠르게 포팅

**단점**:
- ❌ Apple Silicon 전용 (다른 플랫폼 이전 불가)
- ⚠️ CLI·서버 도구 상대적 약함 (Ollama보다 DX 낮음)

---

### B. Ollama

**개요**: 개발자 친화 로컬 LLM 런타임. 단순 CLI·HTTP API.

**2026년 최신**:
- **v0.19+부터 MLX 백엔드 탑재** — Apple Silicon에서 기본 대비 **93% 빠른 decode**
- OpenAI-compatible HTTP API

**장점**:
- ✅ DX 최상 (`ollama run qwen3`)
- ✅ HTTP API — Hermes·Python 어디서든 호출
- ✅ MLX 백엔드로 MLX 성능 활용 가능
- ✅ 모델 자동 다운로드·캐싱

**단점**:
- ⚠️ MLX 백엔드 활성화는 설정 필요
- ⚠️ 세밀한 파라미터 제어는 약함

---

### C. llama.cpp

**개요**: 성숙한 C++ 구현 LLM 런타임.

**장점**:
- ✅ 플랫폼 호환성 최고 (Linux·Mac·Windows)
- ✅ 안정성·생태계
- ✅ 세밀한 제어

**단점**:
- ❌ Apple Silicon 성능은 MLX·Ollama에 밀림
- ⚠️ 빌드·설정 복잡도

---

### D. vLLM (vllm-mlx)

**개요**: 고처리량 배치 추론 서버.

**장점**:
- ✅ 처리량 최대화

**단점**:
- ❌ 개인 사용에 오버킬 (배치가 적음)
- ❌ 설정 복잡

**추천도**: 개인 사용 부적합

---

### Part 1 권장: **Ollama (MLX backend 활성화)**

**선정 근거**:
- MLX 원시 성능 + Ollama DX 결합 (v0.19+의 장점)
- HTTP API로 Hermes·Python 모두 간단 호출
- 모델 교체·관리가 CLI 명령 하나
- Apple Silicon 최적화 + 표준 인터페이스 = 가장 균형

---

## Part 2: 외부 LLM (클라우드)

### A. Claude API (Anthropic)

**장점**:
- ✅ 진지 응답 품질 최상 (컨설팅 톤에 적합, FR-F2)
- ✅ 긴 맥락 추론 강력 (FR-G5 논리 비약 지적)
- ✅ Prompt caching 비용 절감
- ✅ 한국어 품질 우수

**단점**:
- ⚠️ 가격 중간 (Sonnet 기준 $3/MT input)

---

### B. OpenAI (Codex / GPT)

**장점**:
- ✅ 코딩 작업·구조화 출력 강력
- ✅ Codex OAuth 무료 tier 활용 가능 (사용자 이전 언급)
- ✅ 다양한 모델 lineup

**단점**:
- ⚠️ 진지 컨설팅에서 Claude에 다소 밀림 (주관적)
- ⚠️ Codex 무료 tier는 rate limit 엄격

---

### C. OpenRouter

**장점**:
- ✅ 200+ 모델 단일 API로 라우팅
- ✅ 비용·품질 상황별 전환 쉬움

**단점**:
- ⚠️ 한 단계 추가 (latency)
- ⚠️ 비용 표준화 되어 있어도 실제 토큰 가격 변동

---

## 라우팅 규칙 (작업별 모델 선택)

| 작업 | 추천 모델 | 이유 |
|---|---|---|
| 아침 브리핑 생성 (FR-D1) | **Claude** (외부) | 품질 우선, 하루 1회 |
| 대화형 플랜 확정 (FR-D2) | **Claude** (외부) | 맥락 정확도 중요 |
| 저녁 회고 (FR-D3) | **로컬 (Qwen3 등)** | 빈도 높음, 비용·지연 민감 |
| 논리 비약 지적 (FR-G5) | **Claude** (외부) | 긴 맥락·추론 |
| 엔티티 자동 태깅 (FR-G2) | **로컬** | 반복·빠름·프라이버시 |
| 세션 요약 (FR-G1) | **로컬** | 프라이버시·빈도 |
| 컨설팅 톤 응답 (FR-F2) | **Claude** | 품질·근거 |
| 오라클 톤 응답 (FR-F3) | **사전 조회 (LLM 무용)** | 사전에서 한 줄 선택 |
| 학습 세션 대화 (FR-E) | **상황별** (로컬 default → Claude escalation) | 비용 절감 |
| 검색 결과 요약 (FR-B) | **로컬** | 빠름 |

**원칙**:
- **민감 데이터(재무·관계·멘탈)는 로컬 강제**
- **반복·저가치·빠름 필요 → 로컬**
- **진지·드문·품질 중요 → 외부**
- **사전 가능한 건 LLM 안 씀** (오라클 톤, 도메인 키워드 분류 등)

---

## 비용 추정 (월 $20 상한 기준)

| 항목 | 추정 사용량 | 월 비용 |
|---|---|---|
| 아침 브리핑 30일 × Claude Sonnet | 30회 × 5K 토큰 | ~$0.45 |
| 대화형 플랜 확정 30일 × Claude | 30회 × 10K 토큰 | ~$0.90 |
| 주간 리뷰 4회 × Claude | 4회 × 20K 토큰 | ~$0.24 |
| 논리 비약 지적 20회 × Claude | 20회 × 5K 토큰 | ~$0.30 |
| 기타 외부 호출 | 버퍼 | ~$5 |
| **합계 외부 비용** | | **~$7** |
| 로컬 (전기·마모) | Mac mini 24/7 | 실제 비용 $0 추가 |

→ **월 $10 이하로 안정 운영 가능.** $20 상한 여유.

---

## 권장: **로컬 Ollama (MLX) + 외부 Claude (주) + Codex (보조)**

**선정 근거**:
1. **로컬 Ollama**: Apple Silicon 최적 성능 + HTTP API로 통합 용이
2. **외부 Claude**: 진지·드문 작업 품질 보장
3. **Codex OAuth**: 사용자 기존 자원 재활용 (보조 LLM, 비용 0)
4. **라우팅 규칙**: 작업별 모델 선택으로 비용·품질 균형

**LLM 라우터 구현 요구**:
- 단일 함수 `route(task, sensitive, budget) → model`로 추상화
- 설정 파일로 규칙 편집 가능 (사용자 튜닝)
- 장애 시 fallback 체인 (외부 실패 → 로컬)

---

## 위험 & 완화

| 위험 | 완화 |
|---|---|
| Claude API 장애 | 로컬 fallback, 로컬 큐에 쌓고 재시도 (FR-I3) |
| Codex rate limit | Claude 호출로 전환 |
| 로컬 모델 품질 부족 | 외부로 escalation 트리거 (사용자 "진지하게" 재요청시) |
| 비용 상한 근접 | 설정 상한 근접 시 외부 호출 자동 감소, 사용자 경고 |

---

## 출처

- [MLX vs llama.cpp vs Ollama 2026 벤치마크](https://contracollective.com/blog/llama-cpp-vs-mlx-ollama-vllm-apple-silicon-2026)
- [Mac mini M4 LLM Benchmarks 2026](https://www.compute-market.com/blog/mac-mini-m4-for-ai-apple-silicon-2026)
- [2026 Mac Inference Framework](https://macgpu.com/en/blog/2026-mac-inference-framework-vllm-mlx-ollama-llamacpp-benchmark.html)
- [Running LLMs Locally macOS 2026](https://dev.to/bspann/running-llms-locally-on-macos-the-complete-2026-comparison-48fc)
