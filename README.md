# magic-conch-shell

> "The shell has spoken."

당신의 라이프·커리어 맥락을 스스로 축적하는 개인 메모리 + 에이전트 시스템.
가벼운 질문엔 소라고둥처럼, 진지한 질문엔 선택지와 근거로 답한다.

---

## 3 Beliefs

1. **Planning is a conversation, not a command.**
2. **Past you, present you, five-minutes-ago you — all in the shell.**
3. **Answer with data, or answer with nothing.**

---

## 핵심 원칙

- **사용자 outcome 중심**: 성공 기준은 시스템 체크가 아닌 사용자 변화
- **침입성 낮게**: 잔소리·누락 감지 금지. 능동 개입은 스케줄 + 외부 시그널만
- **마크다운 SSoT**: 모든 user data는 `brain/` 하위 평문 마크다운. 캐시는 언제든 재빌드.

---

## Identity 파일

프로젝트 루트의 3개 파일이 Hermes Agent 시스템 프롬프트로 자동 주입된다.

| 파일 | 역할 |
|---|---|
| [`SOUL.md`](SOUL.md) | 인격·톤·금지사항·기본 행동 |
| [`AGENTS.md`](AGENTS.md) | 프로젝트 규약·스킬 라우팅·경계·도구 허용 |
| `USER.md` → `brain/USER.md` | 사용자 프로필 (학습 + 수동, symlink) |

---

## 현재 사용 가능한 CLI (Day 13 기준)

### 데몬 (MCP HTTP 서버 — Milvus 소유자 + 내장 watcher)
```bash
mcs daemon start --daemon   # 백그라운드
mcs daemon status           # pid·포트 확인
mcs daemon stop
```

### 캡처 — 자유 메모 + 구조화 기록
```bash
# 자유 메모 (FR-A1)
mcs capture "가벼운 한 줄"                      # signals/
mcs capture "면접 정리" -d career -e people/jane-smith
mcs capture "..." -t "anthropic-mle-1st-round"  # slug 지정

# KR 백링크 + 진척 자동 업데이트
mcs capture "mock interview 2회" -d career \
    --kr 2026-Q2-career-mle-role.kr-2 --increment 2
# → frontmatter 에 okrs: [...] 기록 + KR current += 2
# → target 도달 시 status 자동 achieved

# 구조화 기록 (FR-A2 — 템플릿 기반)
mcs log                                         # 사용 가능한 템플릿 목록
mcs log interview-note                          # 대화형 필드 입력
mcs log interview-note -f company=companies/anthropic -f round=1차
```

### 조회
```bash
mcs search "면접"                               # 하이브리드 (vector + keyword)
mcs search "LoRA" -d ml -n 5                    # 도메인 필터
mcs search "..." -e people/jane-smith --json    # 엔티티 후처리 + JSON

mcs show 2026-04-20-anthropic-mle-1st           # 본문 + frontmatter (slug)
mcs show signals/2026-04-22-foo --json          # 경로 형태도 허용
```

### OKR — planning SSoT
```bash
# Agent-driven (Hermes skill 대화형, 상태별 skill 자동 호출)
mcs okr new "커리어 OKR 하나 세우자"            # okr-intake + KR agent spawn 옵션
mcs okr new --resume okr-intake-YYYYMMDD-HHMMSS
mcs okr update 2026-Q2-career-mle-role -i       # okr-update 주간 체크인
                                                 # terminal 전이 시 agent archive 프롬프트
mcs okr sync                                    # capture-progress-sync — 오늘 캡처 일괄
mcs okr sync 2026-04-22                         # 특정 일자

# Mechanical (데이터만, Hermes 거치지 않음)
mcs okr list                                    # 기본: 현재 분기·active만
mcs okr list -q all -s all                      # 전 기간·전 상태
mcs okr list -q 2026-Q2 -d career
mcs okr show 2026-Q2-career-mle-role            # KR 포함 상세 + 본문 마크다운
mcs okr update <kr-id> --current 1              # auto-transition: target 도달 시 achieved
mcs okr close 2026-Q2-career-mle-role --note "Offer 수락"
                                                 # cascade: 남은 KR 자동 일괄 상태 전이
mcs okr kr-add <obj-id> --text "연봉 협상" --target 1 --due 2026-06-30
mcs okr kr-list                                 # 기본: 미달성 + active objective만
mcs okr kr-list --due-before 2026-05-15         # 마감 임박
mcs okr kr-list --include-closed                # paused/achieved 부모 포함
```

### KR 전용 에이전트 (동적 생성)
- `mcs okr new` 가 각 KR 저장 후 "agent 만들까?" 물음
- 수락 시 `skills/objectives/<dashed-kr-id>/SKILL.md` 자동 생성
  (KR 목표·부모 맥락·acceptance criteria 포함)
- Hermes 에서 `/<dashed-kr-id>` 로 해당 KR 작업 세션 기동
- KR 이 achieved/missed/abandoned 로 전이되면 `mcs okr update -i` 가
  archive / delete / keep 중 처리 프롬프트
- archive 경로: `archive/skills/objectives/<slug>-<date>/` (미러 구조, `mv` 로 복원)

### 공통 옵션
- `--json` — 모든 조회 명령
- `--direct` — mcs 데몬 우회 (디버깅·오프라인)

**파일 watcher**: 데몬이 떠 있으면 `brain/signals/` 또는 `brain/domains/X/`에
외부 에디터로 `.md` 파일 저장만 해도 frontmatter 자동 보충 + 인덱싱.

---

## 아키텍처 요약

```
Hermes (agent runtime, :8642)              mcs daemon (data, :18342)
  ├─ LLM: Codex gpt-5.4 기본                ├─ 16개 MCP 도구
  │        Ollama qwen3.6 fallback          │   (memory, okr, templates)
  ├─ skills/planner/* 에서 대화 구동        ├─ 하이브리드 검색 (Milvus + bge-m3)
  └─ mcs MCP 도구 호출로 데이터 접근        └─ brain/ 파일 watcher
                  ▲
                  │
  mcs CLI ────────┤
     mechanical → mcs daemon (HTTP MCP)
     agent      → Hermes gateway (/v1/responses)
```

- **mcs** = 데이터 레이어. 메모·엔티티·OKR 저장·검색·재조합.
- **Hermes** = 에이전트 런타임. 모든 LLM 호출·대화·스킬 실행.
- **Brain (`brain/`)** = 마크다운 SSoT. 다른 도구로도 편집 가능.

Hermes 설정 (`~/.hermes/config.yaml`)에 필요한 것:
- `skills.external_dirs: [~/Documents/GitHub/magic-conch-shell/skills]`
- `mcp_servers.mcs: {url: "http://127.0.0.1:18342/mcp/"}`
- `fallback_model: {provider: custom, base_url: "http://127.0.0.1:11434/v1", model: qwen3.6:35b-a3b-mxfp8}`

그리고 `~/.hermes/.env` 에:
- `API_SERVER_ENABLED=true`
- `API_SERVER_KEY=<랜덤>`

`hermes gateway run` 으로 API 서버 기동.
