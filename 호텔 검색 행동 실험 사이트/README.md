# StayTrace — 호텔 검색 행동 로그 실험실

> 프로젝트의 기획 의도, 개발 과정, 현재 구조와 폴더 정리 기준은
> [호텔 프로젝트 종합 보고서](./호텔_프로젝트_종합보고서.md)에서 확인할 수 있습니다.
>
> 운영 사이트 주소, 코드 수정 위치와 배포 흐름은
> [코드·사이트 관리 안내](./프로젝트_코드_사이트_관리_안내.md)에서 확인할 수 있습니다.

실제 예약 사이트와 비슷한 자유 탐색 흐름에서 검색 의도, 노출 순위, 상세 조회, 재검색, 찜, 리뷰, 예약을 SQLite 이벤트 로그로 수집하는 로컬 웹앱입니다. 실제 결제 및 실제 개인정보는 사용하지 않습니다.

## 빠른 실행 (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\seed_hotels.py
python run.py
```

- 사용자 화면: http://127.0.0.1:8000
- 관리자 콘솔: http://127.0.0.1:8000/admin
- 테스트: `pytest -q`

DB는 `data/hotel_behavior.db`에 생성됩니다. 시드 명령은 결정적인 가상 일본 호텔 180개를 만들며, 이미 180개 이상이면 안전하게 건너뜁니다.

## 데이터 구조

| 테이블 | 역할 | PK | 주요 FK |
|---|---|---|---|
| users | 실험 사용자 | user_id | - |
| sessions | 한 방문의 범위 | session_id | user_id |
| hotels | 호텔 마스터 | hotel_id | - |
| searches | 버튼 클릭별 검색 스냅샷/계보 | search_id | user_id, session_id, parent_search_id |
| search_filters | 검색 당시 필터 스냅샷 | search_filter_id | search_id (unique) |
| events | 시간순 행동 원장 | event_id | user_id, session_id, search_id, search_filter_id, hotel_id |
| reviews | 호텔 리뷰 | review_id | hotel_id, user_id |
| reservations | 완료 예약 | reservation_id | user_id, hotel_id, search_id |

보조 `sessions` 테이블은 방문 시작/종료 시각과 사용자 연결을 강제하기 위해 필요합니다. 찜과 노출은 상태 테이블보다 행동 순서가 분석 목적에 중요하므로 `events`에 저장합니다. 노출에는 `(search_id, hotel_id, event_name)` 유일 제약을 두어 같은 검색 결과의 재렌더링 중복을 방지합니다.

## 수집 이벤트

서버 흐름에서 `session_start`, `search_start`, `search_submit`, `search_result_view`, `search_no_result`, `hotel_impression`, `hotel_click`, `hotel_detail_view`, `booking_start`, `booking_complete`, `review_submit`, `page_view`를 기록합니다. UI 동작으로 `filter_open`, `filter_apply`, `sort_change`, `back_to_results`, `wishlist_add/remove`, `booking_cancel`, `exit`를 기록합니다. 추가 값은 JSON(순위, 결과 수, 이전/새 정렬, 예약 번호와 금액 등)으로 보존합니다.

## 화면과 분석

- 등록 → 검색 → 결과/필터/정렬 → 상세/뒤로가기 → 리뷰/찜 → 예약 확인/완료
- `/admin`에서 사용자·세션·검색·재검색·클릭·찜·예약 지표 및 시간순 이벤트 경로 확인
- 7개 핵심 CSV와 조인된 `analysis_event_log.csv`를 관리자 화면에서 UTF-8 BOM 형식으로 다운로드
- 노출→클릭 CTR, 검색 무결과율, 검색별 순위 클릭, 필터/정렬 변경률, 상세 체류 경로, 찜률, 예약 시작·완료 전환율, 세션별 재검색 횟수와 이탈 경로 분석 가능

## 현재 한계

인증·권한, 실제 결제, 객실 재고, 운영용 개인정보 보호/동의, 다중 프로세스 분석 파이프라인은 범위 밖입니다. `exit`는 브라우저의 `pagehide` 특성상 전송이 보장되지 않습니다. 상세 체류시간은 상세 진입과 후속 이벤트 시간 차로 계산하며 별도 duration 필드는 두지 않았습니다.
