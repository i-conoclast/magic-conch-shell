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

## 현재 Phase

**Requirements 정의 중**

이 프로젝트는 구현에 앞서 **요구사항 → 기능 → 설계 → 구현** 순서로 문서화된다.
현재는 요구사항과 기능 목록까지 작성된 상태. 기술 선택·설계는 그 다음 단계.

---

## 디렉토리 안내

| 경로 | 내용 |
|---|---|
| [`docs/requirements/`](docs/requirements/) | 요구사항 정의서 (기술 무관) |
| [`docs/features/`](docs/features/) | 기능 목록 + 우선순위 + 추적표 |
| [`docs/archive/`](docs/archive/) | 이전 설계 초안 (폐기됨) |

**시작점**: [`docs/requirements/00-overview.md`](docs/requirements/00-overview.md) — 1 페이지 요약.

---

## 핵심 원칙

- **기술 무관 요구사항**: requirements/ 와 features/ 에는 구체 제품·라이브러리 이름이 등장하지 않음
- **사용자 outcome 중심**: 성공 기준은 시스템 체크가 아닌 사용자 변화
- **침입성 낮게**: 잔소리·누락 감지 금지. 능동 개입은 스케줄 + 외부 시그널만
