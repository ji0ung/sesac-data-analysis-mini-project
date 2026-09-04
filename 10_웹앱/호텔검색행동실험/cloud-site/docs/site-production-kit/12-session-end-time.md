# 세션 종료 시각 수집 규칙

`EVENT.session_end_time`은 해당 EVENT가 속한 세션의 종료 시각이다.

- 신규 세션: 브라우저의 `pagehide` 시점에 `sendBeacon`으로 `session_end` 이벤트를 보내고 `sessions.ended_at`을 기록한다.
- 직접 로그아웃: `participant_logout` 처리 시 종료 시각을 기록한다.
- 기존 세션: 과거에는 창 닫힘 신호를 수집하지 않았으므로 해당 세션의 마지막 EVENT 발생 시각을 추정 종료 시각으로 사용한다.
- 표시 형식: `YYYY-MM-DD HH:mm:ss KST`

브라우저 강제 종료, 운영체제 종료, 네트워크 단절에서는 종료 신호 전송이 보장되지 않는다. 따라서 신규 기록도 일부 세션에서 종료값이 비어 있을 수 있다. `pagehide`는 새로고침과 페이지 이탈에도 발생하므로 다음 방문에서는 새 세션을 생성한다.

