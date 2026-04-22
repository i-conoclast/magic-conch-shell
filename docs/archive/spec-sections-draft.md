# Archive: section-XX.md 초기 계획 (폐기됨)

이 문서는 magic-conch-shell 스펙 재작성 **이전**의 설계 기록입니다.
아래 내용은 요구사항/설계/구현이 섞여 있어 "무엇을 해결하는가"가 흐렸다는 피드백으로
폐기되고, **Requirements-first 접근**(docs/requirements/, docs/features/)으로 재작성되었습니다.

**보존 이유**: 초기 브레인스토밍 맥락 참조용.
**현재 유효**: ❌ (docs/requirements/ 와 docs/features/ 를 정본으로 사용)

---

## 원래 계획 (폐기)

SPEC.md (v0.1, `docs/archive/SPEC-v0.1.md` 참조)의 16개 섹션을 `spec/section-01.md ~ section-16.md`로 분리하여 구현자가 바로 쓸 수 있는 수준으로 구체화하려 했음.

**16개 섹션**:
1. Vision & Beliefs
2. Scope
3. System Diagram
4. Domain Schema
5. Entity Schema
6. Directory Structure
7. CLI Commands
8. Hermes Skills
9. Voice Rules
10. GBrain 차용 모듈
11. memsearch 통합
12. Contract (plan-tracker)
13. Voice Pipeline
14. Roadmap
15. Open Questions
16. Success Criteria

**폐기 사유**:
- 기술(Hermes / memsearch / Notion / typer / Python 등)과 요구사항이 섞임
- "무엇을 해결하는가"(WHY)보다 "어떻게 구현하는가"(HOW)가 앞섬
- 요구사항 정의서 → 기능 리스트 → 설계 → 구현 순서 원칙 위배

**대체**: `docs/requirements/` (기술 무관 요구사항 정의) + `docs/features/` (기능 목록)
