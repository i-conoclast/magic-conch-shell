# 00. 최종 기술 결정 요약

**작성일**: 2026-04-19
**목적**: 6개 비교 문서의 결정을 하나에 모아 이후 설계의 기준점으로 사용

---

## 결정 요약

| 영역 | 선정 | 대안 (플랜 B) |
|---|---|---|
| 에이전트 프레임워크 | **Hermes Agent** | OpenClaw + 자체 구현 |
| 메모리 엔진 | **memsearch (Milvus Lite)** | sqlite-memory |
| 임베딩 모델 | **BGE-M3 (로컬, 다국어)** | multilingual-e5-large / OpenAI remote |
| 로컬 LLM 런타임 | **Ollama 0.21 (MLX runner)** — 별도 repo [llm-server-template-ollama](https://github.com/i-conoclast/llm-server-template-ollama) | llama.cpp 직접 |
| 로컬 LLM 모델 | **Qwen3.6 35B-A3B mxfp8** (MoE, 38GB, MLX 활성 검증됨) | qwen3.5:35b-a3b (공식 지원 대안), qwen3.6 q4 (GGML만) |
| 외부 LLM (주) | **Codex OAuth (GPT-5.2-codex)** | Claude API |
| 채팅 연동 | **Hermes 내장 iMessage (AppleScript)** | Poke Gate (MCP 중계) |
| 외부 태스크 시스템 | **Notion (기존 유지)** | (대체 비합리적) |
| 캘린더 | **Notion Calendar** | Google / Apple |
| 언어 | **Python 3.11+** | — |
| CLI | **Typer + Rich** | Click 원형 |
| 패키지 매니저 | **uv** | Poetry |

---

## 전체 스택 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                   Mac mini Hub (24/7)                       │
│                                                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │   magic-conch-shell (Python 3.11 + uv)             │    │
│  │   mcs CLI (Typer + Rich)                           │    │
│  │                                                    │    │
│  │   ┌─────────────┐      ┌─────────────────────┐    │    │
│  │   │  Memory     │      │  Planner/Agent      │    │    │
│  │   │  Layer      │      │  Layer              │    │    │
│  │   │             │      │                     │    │    │
│  │   │  memsearch  │      │  Hermes Agent       │    │    │
│  │   │  (Milvus    │      │  (14 platforms,     │    │    │
│  │   │   Lite)     │      │   skills, 3-layer   │    │    │
│  │   │             │      │   memory)           │    │    │
│  │   └──────┬──────┘      └──────────┬──────────┘    │    │
│  │          │                        │               │    │
│  │   ┌──────▼────────────────────────▼──────────┐    │    │
│  │   │   brain/ (마크다운 SSoT)                 │    │    │
│  │   │   .brain/ (캐시 — 재빌드 가능)           │    │    │
│  │   └──────────────────────────────────────────┘    │    │
│  └──────┬──────────────┬──────────────┬──────────────┘    │
│         │              │              │                    │
│         ▼              ▼              ▼                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐            │
│  │ Ollama   │   │ Claude   │   │ Codex OAuth  │            │
│  │ (MLX)    │   │  API     │   │  (보조)      │            │
│  │ :11434   │   │ (품질)   │   │              │            │
│  └──────────┘   └──────────┘   └──────────────┘            │
│                                                             │
│  ┌───────────────────────────────────────────────┐          │
│  │ Hermes 내장 채팅: iMessage + (선택: 기타)      │          │
│  └───────────────────────────────────────────────┘          │
└─────────────────┬───────────────────────┬──────────────────┘
                  │                       │
                  ▼                       ▼
         ┌────────────────┐      ┌──────────────────┐
         │   Notion       │      │   캘린더         │
         │   (plan-       │      │   (TBD)          │
         │   tracker와    │      │                  │
         │   공유)        │      │                  │
         └────────────────┘      └──────────────────┘
                  │
                  ▼
              User (iPhone · Mac 로컬)
```

---

## 각 영역 결정 세부 근거

### 1. Hermes Agent (에이전트 프레임워크)
→ [01-agent-framework.md](01-agent-framework.md)

**핵심 근거**: FR-E1~E5 (워크플로 = 마크다운, 자기 개선) + FR-G1·G2 (메모리 자동화) + FR-H3 (채팅 통합)을 **기본 기능으로 커버**. 4주 MVP 내 실현 가능.

**플랜 B 트리거**: Hermes v0.x 안정성 문제 or iMessage 연동 실패 시 → OpenClaw + 자체 구현

---

### 2. memsearch (메모리 엔진)
→ [02-memory-engine.md](02-memory-engine.md)

**핵심 근거**: "Markdown is the source of truth" 철학 직접 구현. FR-A4·A5·B5 내장. 하이브리드 검색(vector + BM25 + RRF) 품질 최상.

**플랜 B 트리거**: 한국어 검색 품질 부족 시 → sqlite-memory (마크다운 파일 그대로 유지되므로 이전 무손실)

---

### 3. Ollama 0.21 + MLX runner (로컬 LLM)
→ [03-llm-routing.md](03-llm-routing.md)

**핵심 근거**: MLX 성능 + Ollama DX. OpenAI-compatible HTTP API로 Hermes·Python 통합 용이.

**모델**: **Qwen3.6 35B-A3B mxfp8** (MoE, 38GB 디스크, MLX runner 활성 검증됨)
- `OLLAMA_USE_MLX=1` 환경 변수로 MLX backend 활성
- Ollama 0.19+ 필수 (0.21에서 안정화)
- MoE 3B active → 실제 RAM 사용 ~12.7GB (64GB 통합 메모리 내)

**서버 템플릿**: [llm-server-template-ollama](https://github.com/i-conoclast/llm-server-template-ollama) 별도 repo
- config-driven (`configs/*.yaml`)
- launchd 자동 시작 (`./start.sh --install`)
- Tailscale 원격 접속: `OLLAMA_HOST=0.0.0.0:11434` → `http://<tailscale-hostname>.tailXXXX.ts.net:11434/v1`

**주의 (brew services 충돌)**: Homebrew가 기본적으로 `brew services start ollama`로 127.0.0.1 기본 바인딩. 템플릿 사용 시 `brew services stop ollama && brew services disable ollama` 후 `./start.sh <model> --install`로 교체.

**라우팅 원칙**:
- 로컬 기본 (반복·빠름·프라이버시 민감)
- Claude 업스케일 (진지·드문·품질 중요)
- Codex OAuth 보조 (비용 0 재활용)
- 사전 기반 응답(오라클 톤)은 LLM 안 씀

---

### 4. Codex OAuth (외부 LLM 주)
→ [03-llm-routing.md](03-llm-routing.md)

**핵심 근거**:
- 사용자 기존 자원 (Codex OAuth 무료 tier)
- 월 비용 **$0** (플랜 사용량 내)
- GPT-5.2-codex 품질 충분 (진지 응답·컨설팅 톤)

**rate limit 대응**: 초과 시 Ollama 로컬로 fallback.

**변경 이력**: 이전 안은 Claude API였으나 비용 0 우선 원칙으로 Codex OAuth로 변경 (2026-04-19).

**플랜 B 트리거**: Codex OAuth 품질·rate limit에 한계 느끼면 → Claude API 배치 (월 ~$7).

---

### 5. Hermes 내장 iMessage (채팅)
→ [04-chat-integration.md](04-chat-integration.md)

**핵심 근거**: Hermes 선택 시 내장 14 플랫폼 활용. MVP 부담 최저.

**플랜 B 트리거**: Hermes iMessage 불안정 시 → Poke Gate (MCP 중계) or BlueBubbles

---

### 6. Notion (외부 태스크 시스템)
→ [05-external-task.md](05-external-task.md)

**핵심 근거**: 사용자가 이미 사용 중. plan-tracker의 Rollup·집계 구조 재활용. 제로 전환 비용.

**연동 방식**: `notion-client` Python SDK. 기존 Daily Tasks DB 스키마 준수.

---

### 7. Notion Calendar (캘린더)
→ [05-external-task.md](05-external-task.md)

**결정**: 사용자 확인 결과 **Notion Calendar**를 주로 사용.

**구현 접근**:
- Notion API 동일 (notion-client SDK) — 기존 태스크 연동과 같은 경로
- 캘린더 이벤트 읽기·쓰기 표준 API
- plan-tracker·태스크·캘린더 모두 단일 Notion 워크스페이스 내에서 연계

**장점**: Notion 하나로 통합되어 추가 외부 의존성 없음.

---

### 8. Python + Typer + uv (언어·런타임)
→ [06-language-runtime.md](06-language-runtime.md)

**핵심 근거**: plan-tracker와 동일 스택. Hermes Agent가 Python. uv 속도. Typer 프로토타이핑 속도.

---

## 전체 의존성 (pyproject.toml 최종)

```toml
[project]
name = "magic-conch-shell"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  # CLI & UX
  "typer[all]>=0.12",
  "rich>=13",

  # File·데이터
  "watchdog>=4",
  "pydantic>=2",
  "pyyaml>=6",
  "python-frontmatter>=1",

  # HTTP·외부 API
  "httpx>=0.27",
  "notion-client>=2",
  "anthropic>=0.35",
  "openai>=1.30",

  # 메모리 엔진 (PyPI 패키지명 확인 예정)
  # "memsearch>=...",
]

[tool.uv]
dev-dependencies = ["pytest", "ruff", "mypy"]
```

**별도 설치 (pip·brew 등)**:
- Hermes Agent (공식 설치 스크립트)
- Ollama 0.21+ (Homebrew 권장). **[llm-server-template-ollama](https://github.com/i-conoclast/llm-server-template-ollama)로 config·launchd 관리**
- Qwen3.6:35b-a3b-mxfp8 (template `start.sh`가 자동 `ollama pull`)
- Milvus Lite (memsearch 설치 시 동반)

---

## plan-tracker 통합 방식 (2026-04-21 추가)

**결정: 옵션 C — plan-tracker가 MCP 서버로 OKR·KR 데이터를 노출**

### 역할 분담

| 시스템 | 소유 |
|---|---|
| **plan-tracker** | 6 data sources 수집 · aggregation (20 KR · 5 method) · `kr_snapshots` PG 저장 · Notion Rollup sync · **OKR MCP 서비스 노출** |
| **magic-conch-shell** | plan-tracker MCP **클라이언트**로 OKR snapshot·history 읽기. 해석·컨텍스트 제공. |
| **Notion** | 사용자 편집 가능 대시보드 (OKR Master · KR Tracker). plan-tracker가 sync. |

### plan-tracker MCP 서버 규격 (신규)

**위치**: `plan-tracker/src/mcp/plan_tracker_server.py`
**프레임워크**: FastMCP 2.x (magic-conch-shell과 동일 스택)
**전송**: stdio (로컬) + HTTP (원격·향후)
**권한**: 읽기 전용 (쓰기는 plan-tracker 내부 aggregator 전용)

**노출 도구 (MCP tools)**:

```python
# plan-tracker MCP tools
@mcp.tool()
async def okr_snapshot_current(domain: str | None = None) -> dict:
    """Current KR snapshot, optionally filtered by domain."""

@mcp.tool()
async def okr_snapshot_history(weeks: int = 4, domain: str | None = None) -> list[dict]:
    """Weekly OKR history for comparison (weekly reviews)."""

@mcp.tool()
async def okr_kr_detail(kr_id: str) -> dict:
    """Detailed trend/records for a specific KR."""

@mcp.tool()
async def okr_kr_list(domain: str | None = None) -> list[dict]:
    """List KRs (for matching tasks to KRs)."""

@mcp.tool()
async def okr_objective_list() -> list[dict]:
    """List Objectives (O1~O6)."""
```

### magic-conch-shell 측 변경

- `tools/okr.py` = **plan-tracker MCP client wrapper**
- FastMCP 클라이언트로 plan-tracker MCP 서버 호출
- `.env`: `PLAN_TRACKER_MCP_ENDPOINT=stdio:///path/to/plan-tracker/mcp-server`

### Hermes 설정 (`~/.hermes/config.yaml`)

Hermes가 mcs 외에 plan-tracker도 별도 MCP 서버로 추가 가능 (선택):

```yaml
mcp_servers:
  mcs:
    transport: stdio
    command: python ~/magic-conch-shell/mcp/mcs-server.py
  plan_tracker:   # 선택: 직접 접근
    transport: stdio
    command: python ~/plan-tracker/src/mcp/plan_tracker_server.py
```

기본은 **mcs가 plan-tracker MCP 호출하는 경로**. Hermes 직접 접근은 옵션.

### 장점

- ✅ 완전 분리 — mcs가 plan-tracker 스키마 몰라도 됨
- ✅ MCP 표준 — 다른 에이전트(Claude Code 등)도 plan-tracker 사용 가능
- ✅ 버저닝: plan-tracker MCP API를 독립 버전으로 관리
- ✅ 장애 격리 — plan-tracker down → mcs는 OKR 컨텍스트 없이 동작

### 단점 (수용)

- ⚠️ plan-tracker에 MCP 서버 레이어 추가 필요 (~150 lines with FastMCP)
- ⚠️ 배포: plan-tracker가 MCP 서버 프로세스 상주
- ⚠️ 초기 Week 2~3에 plan-tracker 수정 작업 포함

### 구현 순서

1. **magic-conch-shell Week 2**: `tools/okr.py` 스텁 (MCP client, plan-tracker 없으면 graceful degrade)
2. **plan-tracker 수정 (병행)**: MCP 서버 추가
3. **magic-conch-shell Week 3**: plan-tracker MCP 실전 연결
4. **Week 4**: 전체 OKR 플로우 테스트

---

## Library-Level Decisions (2026-04-19 추가)

상위 기술 선택 후 실제 구현에 쓸 **파이썬 라이브러리 레벨**까지 확정.

| 영역 | 라이브러리 | 버전 | 근거 |
|---|---|---|---|
| CLI | typer[all] + rich | >=0.12, >=13 | 2026 표준 (06-language-runtime 참조) |
| Package manager | uv | 최신 | 2026 표준. plan-tracker 동일 스택 |
| File watcher | watchdog | >=4 | macOS FSEvents 네이티브, 안정 |
| Frontmatter | python-frontmatter | >=1 | 커뮤니티 표준 |
| Validation | pydantic | >=2 | DX 우수, 솔로 규모 적합 (msgspec 오버킬) |
| HTTP | httpx | >=0.27 | 비동기 표준 |
| YAML | pyyaml | >=6 | 표준 |
| **MCP server framework** | **fastmcp** | **>=2.0** | **2026 사실상 표준. 공식 SDK 위에 구축, 데코레이터 API, 타입 힌트 자동 스키마** |
| **Codex OAuth client** | **oauth-codex** | **>=0.1** | **2026-03 출시, GPT-5.3-codex 지원, PKCE, sync+async, 디바이스 코드 방식 지원** |
| Notion SDK | notion-client | >=2 | 공식 |
| 메모리 엔진 | memsearch + Milvus Lite | 최신 | 마크다운 SSoT (02-memory-engine 참조) |
| 로컬 LLM | Ollama (HTTP) | **>=0.21** (MLX runner 안정화) | MLX 성능 + DX, llm-server-template-ollama 활용 |

**별도 설치 (pip·brew 등 — pyproject.toml 밖)**:
- Hermes Agent (공식 설치 스크립트)
- Ollama 0.21+ (Homebrew 권장). **[llm-server-template-ollama](https://github.com/i-conoclast/llm-server-template-ollama)로 config·launchd 관리**
- Qwen3.6:35b-a3b-mxfp8 (template `start.sh`가 자동 `ollama pull`)
- memsearch의 Milvus Lite는 Python 패키지 동반 (별도 설치 불필요)

**pyproject.toml 초안**:

```toml
[project]
name = "magic-conch-shell"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
  # CLI & UX
  "typer[all]>=0.12",
  "rich>=13",

  # File & data
  "watchdog>=4",
  "pydantic>=2",
  "pyyaml>=6",
  "python-frontmatter>=1",

  # HTTP & external APIs
  "httpx>=0.27",
  "notion-client>=2",

  # LLM
  "oauth-codex>=0.1",        # ⭐ Codex OAuth (GPT-5.3-codex, PKCE)
  # "anthropic>=0.35",       # 선택: Claude API 비상용

  # MCP server
  "fastmcp>=2.0",            # ⭐ 2026 표준

  # Memory engine
  # "memsearch>=...",        # PyPI 이름 설치 시 확인

  # Ollama (옵션, httpx로 대체 가능)
  "ollama>=0.3",
]

[tool.uv]
dev-dependencies = ["pytest", "ruff", "mypy"]
```

---

## 사용자 확인 완료 (2026-04-19)

| 질문 | 답 |
|---|---|
| 캘린더 | **Notion Calendar** |
| Hermes 설치 경험 | **없음** → Week 2 초반에 학습·설치 시간 할당 |
| Mac mini 스펙 | **M4 Pro 64GB** (Qwen3.6 35B-A3B mxfp8 ~12.7GB 실사용, 여유 많음) |
| 외부 LLM | **Codex OAuth** (Claude API 아님) |
| 임베딩 모델 | **BGE-M3** (로컬·다국어) |

## 열린 질문 (구현 단계에서 확인)

| # | 질문 | 결정 기한 |
|---|---|---|
| 1 | iCloud 계정 분리 정책 (Mac mini 전용 ID 만들지) | Week 3 iMessage 구현 시 |
| 2 | BGE-M3 한국어 검색 품질 실측 — 기대치 미달 시 대체 | Week 1 검증 |
| 3 | Hermes v0.7.x 버전 고정 (API 안정성) | 설치 시점 |
| 4 | Codex OAuth rate limit 실측 후 보조 LLM 필요 여부 | Week 2 사용량 확인 후 |

---

## 다음 단계

1. **00-architecture.md** 작성 — 위 스택을 구현 아키텍처로 변환
2. **02-data-model.md** 작성 — brain/ 파일 구조·엔티티 스키마·프론트매터 명세
3. **fr-notes/FR-A1.md ~ FR-I3.md** — 41개 FR 각각을 위 스택으로 구현하는 노트
4. **integration-contracts.md** — Notion DB 필드 계약, Hermes skill 포맷 등
