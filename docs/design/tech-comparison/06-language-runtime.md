# 06. Language & Runtime 비교

**작성일**: 2026-04-19
**목적**: 구현 언어·CLI 프레임워크·패키지 매니저 선택

---

## 요구사항 재확인

| FR / NFR | 선정 영향 |
|---|---|
| FR 전반 | 생태계·라이브러리 가용성 |
| NFR-02 지연 | 성능 (하지만 지연 요구는 낮음) |
| NFR-07 유지보수성 | 솔로 운영 가능한 언어·도구 |
| 사용자 컨텍스트 | 기존 plan-tracker는 Python 3.11 + uv |

---

## Part 1: 언어

### A. Python 3.11+

**장점**:
- ✅ **사용자 기존 스택과 일치** (plan-tracker Python 3.11)
- ✅ AI·에이전트 생태계 최대 (Hermes Agent 자체가 Python)
- ✅ `notion-client`, `httpx`, `watchdog`, `rich`, `typer` 등 필요 라이브러리 전부 존재
- ✅ 마크다운 처리·YAML 파싱 표준 라이브러리
- ✅ 학습·유지 부담 낮음 (기존 숙련도 재활용)

**단점**:
- ⚠️ 성능 — 하지만 FR 요구사항(캡처 2초·브리핑 30초)은 여유로움
- ⚠️ 타입 체크는 약함 — mypy로 보완

**추천도**: ⭐⭐⭐⭐⭐

---

### B. TypeScript / Node.js

**장점**:
- ✅ 비동기 I/O 강력
- ✅ 타입 시스템 견고
- ✅ Poke Gate 등 일부 도구가 JS 기반

**단점**:
- ❌ **사용자 스택과 불일치** (plan-tracker Python)
- ❌ Hermes Agent 통합이 Python보다 복잡
- ❌ 이중 언어 유지 부담 (plan-tracker + 이것)

**추천도**: ⭐⭐ — Python이 압도적으로 나음

---

### C. Go

**장점**:
- ✅ 성능·컴파일 산출물 배포 쉬움
- ✅ 동시성 모델

**단점**:
- ❌ AI·에이전트 생태계 약함
- ❌ 학습 곡선·솔로 운영 부담
- ❌ Hermes Agent 직접 통합 불가 (HTTP·MCP만)

**추천도**: ⭐ — 불필요

---

### D. Rust

**장점**:
- ✅ 성능 최고·안전성

**단점**:
- ❌ AI 생태계 최약
- ❌ 학습 곡선 최고
- ❌ MVP 4주 부적합

**추천도**: ⭐ — 부적합

---

**Part 1 권장: Python 3.11+**

---

## Part 2: CLI 프레임워크

### A. Typer

**개요**: FastAPI 팀이 만든 CLI 프레임워크. Click 기반, 타입 힌트로 선언.

**2026년 최신**:
- Rich 통합으로 자동 포맷팅
- Click보다 **3배 빠른 프로토타이핑** (AI 툴 반복 개발에 적합)
- `typer[all]` 설치로 Rich 자동 통합

**장점**:
- ✅ 타입 힌트 기반 — 선언 간결
- ✅ Rich 통합 기본 — 예쁜 출력 자동
- ✅ 자동 help 생성

**단점**:
- ⚠️ 복잡한 중첩 서브커맨드는 Click 원형이 더 유연

**추천도**: ⭐⭐⭐⭐⭐

---

### B. Click

**개요**: Typer의 기반. 성숙한 Python CLI 프레임워크.

**장점**:
- ✅ 가장 성숙
- ✅ 세밀한 제어
- ✅ 중첩 서브커맨드 자유도

**단점**:
- ⚠️ 보일러플레이트 많음 (Typer 대비)

**추천도**: ⭐⭐⭐⭐ — Typer의 하위 호환

---

### C. argparse (표준 라이브러리)

**장점**:
- ✅ 의존성 0

**단점**:
- ❌ 개발 경험 낮음
- ❌ 타입 검증·자동 help 약함

**추천도**: ⭐⭐ — 최소 프로젝트에만

---

**Part 2 권장: Typer + Rich**

---

## Part 3: 패키지 매니저

### A. uv (Astral)

**개요**: 2024~2026년 급부상한 Rust 구현 초고속 Python 패키지 매니저.

**2026년 최신**:
- 스크립트 단위 의존성 관리 (`# /// script` 헤더)
- CLI 앱 설치 (`uv tool install`)
- Poetry·pip-tools 대체재

**장점**:
- ✅ **속도**: pip/Poetry 대비 10~100배
- ✅ **사용자 기존 스택** (plan-tracker가 uv)
- ✅ 단일 바이너리 (Python 가상환경 + 의존성 + 실행)
- ✅ `uv sync`로 lock file 기반 재현성

**단점**:
- ⚠️ 상대적 신생 (2024 출시) — API 변경 이력 있음

**추천도**: ⭐⭐⭐⭐⭐

---

### B. Poetry

**장점**:
- ✅ 성숙한 lock file·퍼블리싱 워크플로

**단점**:
- ⚠️ uv보다 느림
- ⚠️ 사용자 스택과 불일치

**추천도**: ⭐⭐⭐

---

### C. pip + requirements.txt

**단점**:
- ❌ lock file 없음
- ❌ 재현성 약함

**추천도**: ⭐ — 유지 부담 높음

---

**Part 3 권장: uv**

---

## Part 4: 기타 핵심 라이브러리

| 라이브러리 | 용도 | 추천 이유 |
|---|---|---|
| `rich` | 터미널 포맷 (표·패널·진행률) | Typer와 기본 통합 |
| `watchdog` | 파일 변경 감지 (FR-A4) | 크로스 플랫폼 표준 |
| `httpx` | 비동기 HTTP (Notion·Claude API) | requests 상위 호환 |
| `pydantic 2.x` | 데이터 모델·검증 | 타입 기반, FastAPI와 동일 |
| `pyyaml` | 프론트매터 파싱 | 표준 |
| `python-frontmatter` | 마크다운 + 프론트매터 조합 | 마크다운 처리 전문 |
| `notion-client` | Notion API | 공식 SDK |
| `anthropic` | Claude API | 공식 SDK |
| `openai` | OpenAI API | 공식 SDK |

---

## 최종 스택

```
언어: Python 3.11+
패키지 매니저: uv
CLI 프레임워크: Typer + Rich
핵심 라이브러리:
  - watchdog (파일 감지)
  - httpx (HTTP)
  - pydantic 2.x (데이터 모델)
  - python-frontmatter (마크다운)
  - notion-client, anthropic, openai (SDK)
```

---

## 위험 & 완화

| 위험 | 완화 |
|---|---|
| uv API 변경 | lock file 사용 + 버전 고정 |
| Python 3.11 → 3.12 마이그레이션 | pyproject.toml에 `>=3.11` 명시 |
| Hermes Agent Python 버전 충돌 | 독립 venv + Hermes는 별도 설치 |

---

## pyproject.toml 초안

```toml
[project]
name = "magic-conch-shell"
version = "0.1.0"
description = "Personal life brain + agent"
requires-python = ">=3.11"
dependencies = [
  "typer[all]>=0.12",
  "rich>=13",
  "watchdog>=4",
  "httpx>=0.27",
  "pydantic>=2",
  "pyyaml>=6",
  "python-frontmatter>=1",
  "notion-client>=2",
  "anthropic>=0.35",
  "openai>=1.30",
  # memsearch — 별도 설치 필요 (PyPI 패키지명 확인)
]

[tool.uv]
dev-dependencies = ["pytest", "ruff", "mypy"]
```

---

## 출처

- [Typer vs Click 2026](https://devtoolbox.dedyn.io/blog/python-click-typer-cli-guide)
- [uv Python Scripts](https://docs.astral.sh/uv/guides/scripts/)
- [Typer with Rich](https://dasroot.net/posts/2026/01/building-cli-tools-with-typer-and-rich/)
- [uv for CLI Apps](https://mathspp.com/blog/using-uv-to-build-and-install-python-cli-apps)
