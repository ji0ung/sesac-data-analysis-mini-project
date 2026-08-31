# 현재 아키텍처와 코드 지도

## 1. 실행 구조

```text
브라우저
  └─ app/page.tsx (사용자·관리자 단일 UI와 상태 전환)
       ├─ app/globals.css, app/rooms.css
       └─ /api/data
            └─ app/api/data/route.ts (검색, 로그, 객실, 예약, 관리자 API)
                 ├─ app/hotel-data.ts (호텔 카탈로그 원천/생성 규칙)
                 ├─ db/schema.ts (Drizzle 테이블 정의)
                 └─ Cloudflare D1 DB 바인딩
```

빌드 산출물은 vinext가 Cloudflare Worker 호환 ESM으로 만든다. `.openai/hosting.json`의 `DB` 논리 바인딩은 배포 플랫폼이 실제 D1 자원에 연결한다.

## 2. 주요 파일

| 파일 | 역할 | 수정 시 확인할 항목 |
|---|---|---|
| `app/page.tsx` | 화면, 상태, 사용자 동작, API 호출 | 화면 전환, 중복 이벤트, 모바일 |
| `app/api/data/route.ts` | 단일 데이터 API와 실험 로직 | DB 저장, 조건 필터, 이벤트 속성 |
| `app/hotel-data.ts` | 호텔·지역·리뷰 데이터 생성 | 개수, 중복, 세부지역 분포 |
| `app/globals.css` | 전체 레이아웃과 관리자 UI | 독립 스크롤, 고정 버튼, 반응형 |
| `app/rooms.css` | 객실·달력·상세 스타일 | 작은 화면, 판매 마감 상태 |
| `db/schema.ts` | 애플리케이션 ORM 스키마 | migration과 실제 D1 일치 |
| `drizzle/*.sql` | 누적 DB migration | 기존 데이터 보존, 역호환 |
| `scripts/expand-hotel-catalog.mjs` | 호텔 카탈로그 확장 보조 | 생성 규칙과 현재 소스 동기화 |
| `public/hotel-images/` | 숙소 특성 기반 이미지 | 라이선스·실제 사진 오인 방지 |
| `public/staytrace-project-report.md` | 사용자용 기획 보고서 | 실험 비율과 기능 최신화 |
| `docs/site-production-kit/` | 제작·운영 인수인계 | 코드 변경 시 함께 갱신 |
| `.openai/hosting.json` | 기존 Sites 프로젝트와 DB 논리 바인딩 | project_id 변경 금지, 비밀 저장 금지 |

## 3. 구현 선택의 배경

최초 기획은 Python FastAPI·SQLite·Jinja2였지만, 현재 운영판은 계속 접근 가능한 공개 클라우드 배포와 반응형 UI, D1 영속 저장을 위해 TypeScript·React·vinext·Cloudflare D1 구조를 사용한다. 기능 목표와 분석 데이터 모델은 유지하되 실행 스택만 배포 환경에 맞게 변경됐다.

## 4. 상태 관리

- `sessionStorage`: 탭 생명주기 동안 참여자/세션 상태 유지
- React state: 현재 화면, 검색 초안과 적용값, 결과, 선택 호텔, 갤러리, 예약 단계
- D1: 사용자, 세션, 검색, 이벤트, 예약 등 영속 데이터
- 결정적 해시: 세션 실험군, 옵션 불일치, 날짜별 객실 판매 마감

## 5. API 원칙

`/api/data`는 요청의 `action` 값에 따라 작업을 분기한다. 모든 쓰기는 서버에서 ID와 시간을 만들며, 사용자가 이름을 다시 입력하면 기존 동일 사용자 ID를 재사용한다. 검색 제출 시 검색 레코드, 필터 정보, 결과 노출 이벤트가 같은 검색 문맥을 공유해야 한다.

## 6. 변경 시 결합 관계

- 새 필터: UI 입력 → 검색 요청 → 서버 필터 → SEARCH 조건 → SEARCH_FILTER/CSV → 오류 실험 → 보고서
- 새 행동: UI 버튼 → API event → EVENT 관리자 표/CSV → KPI 또는 경로 분석 → 문서
- 새 호텔 속성: 데이터 생성 → Hotel 타입 → 검색/카드/상세 → 호텔 CSV → 필요 시 migration
- 새 예약 상태: 객실 UI → 서버 검증 → RESERVATION → booking 이벤트 → 관리자 지표

