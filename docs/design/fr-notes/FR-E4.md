# FR-E4: DIY 워크플로 추가

**카테고리**: E. Sessions
**우선순위**: 중간 (MVP 포함)

---

## 1. Overview

사용자가 직접 `agents/{name}.md` + `commands/{name}.md` 작성해 **새 workflow 추가**. 재시작 불필요, 즉시 사용 가능.

---

## 2. 관련 컴포넌트

- **Agents**: `agents/{name}.md`
- **Commands**: `commands/{name}.md`
- **Templates**: `templates/agent-template.md`, `templates/command-template.md`
- **State**: `brain/session-state/{name}/` 자동 생성

---

## 3. 사용자 워크플로

### A. 템플릿 복사
```bash
$ mcs workflow init mock-debate
  ✓ agents/mock-debate.md created (from template)
  ✓ commands/mock-debate.md created (from template)
  ✓ brain/session-state/mock-debate/ created
  Edit agents/mock-debate.md to define persona and flow.
```

### B. 편집
사용자가 `agents/mock-debate.md`·`commands/mock-debate.md` 수정.

### C. 즉시 사용
```
/mock-debate    # 슬래시 명령
mcs mock-debate # CLI
```

재시작 없음.

---

## 4. agent-template.md

```markdown
---
name: {name}
description: (Describe what this workflow does in one sentence — used for auto-detection)
tools: [memory, llm]
model: ollama-local
isolation: fork
state_path: brain/session-state/{name}/
max_turns: 30
memory: persistent
---

# {Name}

## Persona
(Describe the agent's persona: role, tone, expertise)

## Session structure
1. (How does a session start?)
2. (What's the typical flow?)
3. (How does it end?)

## Rules
- (Constraints on the agent's behavior)
```

## command-template.md

```markdown
---
name: {name}
description: Start {name} session
agent: {name}
---

# /{name}

Invokes the {name} workflow agent.
```

---

## 5. 문법 오류 격리

DIY 파일이 잘못되면:
- 해당 agent/command만 로드 실패
- 다른 workflow는 정상
- `mcs doctor`에서 오류 확인

```python
# engine/loader.py
def load_agents():
    agents = {}
    errors = []
    for path in Path("agents").glob("*.md"):
        try:
            post = frontmatter.load(path)
            validate_agent_schema(post.metadata)
            agents[post.metadata["name"]] = post
        except Exception as e:
            errors.append({"path": str(path), "error": str(e)})
    return agents, errors
```

사용자에게 명확한 에러:
```
$ mcs doctor
✓ 5 workflows loaded
❌ 1 workflow failed:
  agents/mock-debate.md: missing required field 'tools'
```

---

## 6. 테스트 포인트

- [ ] `mcs workflow init {name}` → 3개 파일 생성
- [ ] 문법 맞는 새 agent → 재시작 없이 호출 가능
- [ ] 문법 틀림 → 해당 것만 실패, 나머지 정상
- [ ] 명령으로 호출 (`/{name}`) + 자동 감지 (키워드·LLM) 둘 다 작동
- [ ] state.yaml 비어있는 상태에서 첫 세션 성공

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| 사용자가 템플릿 불완전하게 채움 | 필수 필드 검증. 에러 메시지로 어디가 부족한지 알림. |
| 이름 충돌 (기존과 같은 이름) | `init` 명령에서 존재 여부 체크 |
| state_path 경로 겹침 | `{name}`과 폴더 이름 1:1. 충돌 불가능 (init이 만들므로). |

---

## 8. 관련 FR

- **FR-E1** 워크플로 파일
- **FR-E2** 호출 방법
- **FR-E5** 자동 승격 (반대 방향: 시스템이 만든 draft를 사용자가 편집)

---

## 9. 구현 단계

- **Week 3 Day 7**: 템플릿 파일 작성
- **Week 4 Day 1**: `mcs workflow init` 커맨드
- **Week 4 Day 2**: 로더 + 격리 오류 처리
