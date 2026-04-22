# FR-H3: 채팅 앱 양방향 (iMessage)

**카테고리**: H. Integration
**우선순위**: 높음 (MVP 필수)

---

## 1. Overview

아침 브리핑·플랜 확정·회고가 **iMessage 양방향**으로 이루어짐. Hermes 내장 iMessage adapter 활용.

---

## 2. 관련 컴포넌트

- **Hermes 내장 adapter**: AppleScript 기반 (iMessage 송·수신)
- **MCP tool**: `hermes.send_imessage`
- **전제**: Mac mini에 iCloud 계정 로그인

---

## 3. 데이터 플로우

### Send
```
mcs skill → hermes.send_imessage(recipient, text)
   → Hermes adapter (AppleScript)
     tell application "Messages"
       send "text" to buddy "recipient"
     end tell
   → 성공 확인 → 로그
```

### Receive
```
사용자가 iMessage 발송
   → Mac mini Messages DB (chat.db) 신규 엔트리
   → Hermes polling / FSEvents 감지 (~초)
   → Hermes가 conch-answer skill 실행
   → 응답 생성 → send back
```

---

## 4. 제한·주의

### iCloud 계정
- Mac mini에 iCloud 계정 로그인 **필수**
- **옵션 A**: 사용자 본인 계정 → Mac mini가 모든 iMessage 수신 (개인/업무/가족 대화 모두 옴)
- **옵션 B**: 별도 Apple ID + 별도 번호 → 시스템 전용 대화만 (추천, 번거로움)

**MVP**: 옵션 A로 시작 + Hermes에서 **필터링** (특정 발신자만 응답).

```yaml
# ~/.hermes/config.yaml
platforms:
  imessage:
    enabled: true
    allowed_senders:
      - "+8210XXXXXXX"     # 사용자 본인 번호
```

### 수신 지연
- FSEvents 기반이라 **1~5초 지연** 가능
- 긴 메시지 스레드 → polling 필요할 수 있음

---

## 5. 구현 노트

Hermes 내장이라 우리 직접 구현 최소. 필요한 건:

### 확인
- Mac mini에 Messages 앱 로그인
- Hermes config에 `imessage` 활성화
- AppleScript 실행 권한 허용 (시스템 설정 → 보안)

### MCP tool wrapping (옵션)
```python
# tools/hermes.py (mcs 쪽에서 Hermes 호출용)
async def send_imessage(recipient: str, text: str) -> dict:
    """Send iMessage via Hermes."""
    # Hermes의 CLI or API 호출
    result = await subprocess.run(
        ["hermes", "send", "imessage", recipient, "--text", text],
        capture_output=True, text=True,
    )
    return {"status": "sent" if result.returncode == 0 else "failed"}
```

(또는 Hermes가 제공하는 Python SDK 사용)

---

## 6. 테스트 포인트

- [ ] Mac mini에서 송신 테스트 (hermes.send_imessage)
- [ ] iPhone에서 수신 확인
- [ ] iPhone에서 답장 → Mac mini Hermes 수신 → conch-answer 응답
- [ ] 3턴 이상 대화에서 맥락 유지 (Hermes conversational memory)
- [ ] Hermes down 시 fallback (터미널 출력)
- [ ] 필터링: 다른 사람 메시지 무시

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| iCloud 계정 2FA 문제 | Mac mini에 먼저 로그인 완료 후 운영 |
| Messages 앱 미실행 | launchd로 Messages 자동 실행 + keep-alive |
| AppleScript 권한 거절 | 설치 가이드에 권한 허용 단계 포함 |
| 수신 지연 심함 | polling 주기 조정 (기본 1초) |
| iMessage 장애 (Apple 측) | 터미널 출력 fallback (doctor 경고) |

---

## 8. 관련 FR

- **FR-D1** 아침 브리핑 (주 송신 경로)
- **FR-D2** 플랜 확정 (양방향)
- **FR-D3** 저녁 회고 (양방향)
- **FR-I3** 장애 대응 (fallback)

---

## 9. 구현 단계

- **Week 2 Day 6**: Mac mini Hermes 설치 + iMessage 설정
- **Week 3 Day 2**: 단순 송신 테스트
- **Week 3 Day 3**: 양방향 대화 (plan-confirm)
- **Week 4 Day 1**: 필터링·fallback
