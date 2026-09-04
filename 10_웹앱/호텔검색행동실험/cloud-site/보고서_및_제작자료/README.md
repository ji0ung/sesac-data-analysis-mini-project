# StayTrace 보고서 및 제작자료

이 폴더는 StayTrace 호텔 검색 행동 실험 사이트의 보고서, 데이터 명세, 제작 프롬프트, 운영 문서와 배포용 묶음을 한곳에서 확인하기 위한 자료 모음이다.

## 먼저 볼 문서

1. [프로젝트 종합 보고서](./01-StayTrace-프로젝트-보고서.md)
2. [현재 데이터 콘솔 명세](./데이터-콘솔-최종-명세.md)
3. [실제 정보와 가상 데이터 구분](./실제정보-가상데이터-구분표.md)
4. [제작 문서 안내](./02-제작문서/README.md)
5. [전체 제작자료 ZIP](./03-배포자료/staytrace-site-production-kit.zip)

## 제작 문서 구성

- `01-product-spec.md`: 서비스 목적과 화면·기능 명세
- `02-codex-master-prompt.md`: 사이트 재구축용 통합 프롬프트
- `03-codex-change-prompts.md`: 기능별 변경 요청 프롬프트 기록
- `04-architecture-and-code-map.md`: 기술 구조와 주요 코드 위치
- `05-data-event-experiment.md`: 데이터 관계와 이벤트·실험 설계
- `06-setup-test-deploy.md`: 실행·검증·배포 절차
- `07-operations-and-security.md`: 운영·개인정보·보안 주의사항
- `08-requirements-history.md`: 요구사항 변경 이력
- `09-release-checklist.md`: 배포 전 점검표
- `10-notion-export-schema.md`: 기존 데이터 내보내기 명세 참고본

## 현재 운영 정보

- 사용자 및 관리자 화면: https://staytrace-hotel-lab.dlthdl321.chatgpt.site
- 공개 보고서: https://staytrace-hotel-lab.dlthdl321.chatgpt.site/staytrace-project-report.md
- 공개 제작자료 ZIP: https://staytrace-hotel-lab.dlthdl321.chatgpt.site/staytrace-site-production-kit.zip
- 데이터 콘솔은 화면 진입 시 별도의 지정 코드가 필요하다.

## 정본 위치

이 폴더는 확인하기 쉬운 현재 시점의 자료 모음이다. 사이트에 공개되는 보고서의 정본은 `public/staytrace-project-report.md`, 제작 문서의 정본은 `docs/site-production-kit/`이다. 실제 실행 코드는 `app/`, 데이터베이스 구조는 `db/`와 `drizzle/`에 있다.
