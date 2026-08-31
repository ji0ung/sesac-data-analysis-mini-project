# StayTrace 사이트 제작 자료 모음

이 폴더는 StayTrace 호텔 검색 행동 연구 웹앱을 이해하고, 수정하고, 다시 배포하는 데 필요한 문서를 한곳에 모은 제작 인수인계 패키지다.

## 문서 구성

1. [01-product-spec.md](01-product-spec.md) — 제작 목적, 화면, 기능, 데이터와 실험 명세
2. [02-codex-master-prompt.md](02-codex-master-prompt.md) — 신규 작업공간에서 사이트를 재구축할 때 사용하는 통합 프롬프트
3. [03-codex-change-prompts.md](03-codex-change-prompts.md) — 유지보수·데이터·분석·배포용 대화 프롬프트 모음
4. [04-architecture-and-code-map.md](04-architecture-and-code-map.md) — 현재 기술 구조와 파일별 코드 역할
5. [05-data-event-experiment.md](05-data-event-experiment.md) — DB, 이벤트, 오류 실험, 분석 지표
6. [06-setup-test-deploy.md](06-setup-test-deploy.md) — 설치, 실행, 검증, 배포 절차
7. [07-operations-and-security.md](07-operations-and-security.md) — 운영, 백업, 복구, 보안 및 개인정보 원칙
8. [08-requirements-history.md](08-requirements-history.md) — 최초 기획부터 현재 버전까지의 요구사항 변천
9. [09-release-checklist.md](09-release-checklist.md) — 수정 전후 확인 체크리스트
10. [10-notion-export-schema.md](10-notion-export-schema.md) — Notion 기획서 기준 CSV 칼럼 명세

## 현재 구현 요약

- 공개 사용자 화면과 동일 앱 안의 관리자 데이터 콘솔
- 일본 5개 도시, 지역별 200개씩 총 1,000개 숙소 데이터
- 호텔별 대표 리뷰 5개, 총 5,000개 리뷰
- 검색·필터·정렬·상세·갤러리·객실·예약 모의 흐름
- 사용자 이름 기반 동일 사용자 식별과 탭 세션 유지
- EVENT 중심 행동 로그와 테이블별 CSV 내보내기
- 삭제 데이터 휴지통 및 복구
- 정상군 75%, 오류 실험군 25%의 재현 가능한 실험 배정
- 전체 기대 발생률: 객실 옵션 불일치 약 8%, 키워드 결과 불일치 약 5%

## 원본 코드 위치

실제 실행 코드는 문서 폴더가 아니라 프로젝트 루트의 `app/`, `db/`, `drizzle/`, `public/`, `scripts/`에 있다. 이 문서들은 코드를 복제하지 않고 현재 소스 파일을 정본으로 참조한다.

## 중요 주의사항

- 호텔명 일부는 공개 숙박업소 정보를 참고했지만 가격, 객실 재고, 평점, 리뷰, 시설 가용성은 연구용 시뮬레이션 값이다.
- 시설 이미지도 실제 호텔 사진이 아닌 숙소 특성 기반 이미지다.
- 오류 비율은 Agoda의 공식 실측값이 아니다. 공개 문서에서 확인 가능한 시설·재고 불일치 가능성을 바탕으로 정한 연구용 보수적 설계값이다.
- 실제 결제나 실제 예약은 발생하지 않는다.
- API 키, 저장소 토큰, 배포 자격 증명은 코드나 문서에 기록하지 않는다.
