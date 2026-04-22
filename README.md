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
