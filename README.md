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

## 현재 사용 가능한 CLI (Day 7 기준)

```bash
# 데몬 (MCP HTTP 서버, Milvus 소유자 + 내장 watcher)
mcs daemon start --daemon   # 백그라운드
mcs daemon status           # 상태·pid·포트 확인
mcs daemon stop

# 메모 캡처 (기본: 데몬 경유, --direct로 우회 가능)
mcs capture "가벼운 한 줄"                      # signals/
mcs capture "면접 정리" -d career -e people/jane-smith
mcs capture "..." -t "anthropic-mle-1st-round"  # slug 지정

# 검색
mcs search "면접"                               # 하이브리드 (vector + keyword)
mcs search "LoRA" -d ml -n 5                    # 도메인 필터
mcs search "..." -e people/jane-smith --json    # 엔티티 후처리 + JSON
```

**파일 watcher**: 데몬이 떠 있으면 `brain/signals/` 또는 `brain/domains/X/`에
외부 에디터로 `.md` 파일 저장만 해도 frontmatter 자동 보충 + 인덱싱.
