# 설치, 실행, 테스트와 배포

## 1. 준비 사항

- Node.js 22.13 이상
- npm
- Git
- Sites와 D1을 사용할 수 있는 Codex 환경

## 2. 로컬 설치

프로젝트 루트에서 실행한다.

```powershell
npm install
npm run dev
```

Windows에서 `npm run build`의 Unix형 환경변수 문법이 동작하지 않으면 다음처럼 실행한다.

```powershell
$env:WRANGLER_LOG_PATH='.wrangler/wrangler.log'
npx vinext build
```

개발 서버가 출력한 Local URL을 브라우저에서 연다. 포트 번호를 문서에 고정하지 말고 실제 출력값을 사용한다.

## 3. DB 변경

1. `db/schema.ts` 수정
2. migration 생성

```powershell
npm run db:generate
```

3. 생성된 `drizzle/*.sql`을 검토한다.
4. 기존 열 삭제나 이름 변경보다 추가 migration을 선호한다.
5. 기존 데이터 보존과 관리자 CSV 호환성을 확인한다.

## 4. 필수 테스트 시나리오

### A. 정상 예약

참여자 입력 → Tokyo 검색 → 호텔 상세 → 이미지 탐색 → 판매 가능 객실 → 예약 확인 → 예약 완료.

확인: 같은 session_id, 검색 ID 연결, impression rank, gallery, room, booking 이벤트.

### B. 재검색

Osaka 검색 → 상세 옵션 변경 → 적용 버튼 → 다른 호텔 상세 → 결과 복귀.

확인: 새 search_id, 직전 parent_id, 입력/체크 시 불필요한 search_submit 없음.

### C. 예약 취소

호텔 상세 → 객실 선택 → 예약 확인 → 취소.

확인: 오류 없이 이전 상세 상태 복귀, booking_cancel 1회 기록.

### D. 오류 노출

여러 이름/세션으로 스파·발코니 등 옵션과 한글 키워드를 검색한다.

확인: 일부에서만 불일치, 동일 세션 조합 재현, 정상군에는 의도적 오류 없음.

### E. 관리자

모든 데이터 탭 확인 → CSV 다운로드 → 행 삭제 → 휴지통 → 복구.

확인: 다운로드 열과 표 일치, 복구 후 원래 데이터셋에 재등장.

### F. 모바일

작은 화면에서 검색, 옵션 패널, 호텔 카드, 고정 뒤로가기, 객실과 관리자 표를 확인한다.

## 5. 배포 원칙

- `.openai/hosting.json`에 기존 `project_id`가 있으면 반드시 재사용한다.
- 새 사이트를 만들거나 URL을 바꾸지 않는다.
- 성공한 로컬 빌드와 정확히 같은 커밋을 저장·배포한다.
- 소스 저장소 쓰기 토큰은 명령 단위로만 사용하고 파일이나 Git 설정에 저장하지 않는다.
- D1 migration이 있으면 빌드 패키지에 포함한다.
- 공개 사이트이므로 기존 공개 접근 정책을 보존한다.

## 6. 배포 후 확인

- 사용자 URL HTTP 200
- `/staytrace-project-report.md` HTTP 200
- 사용자 등록과 검색 API 성공
- 관리자 데이터 로드 성공
- 콘솔에 치명적 오류 없음

## 7. 되돌리기

문제가 생기면 파괴적인 Git 초기화를 하지 않는다. 이전에 저장된 정상 Sites 버전을 다시 배포하거나, 수정 커밋을 새 커밋으로 되돌린 뒤 재빌드·재배포한다. DB migration은 이미 적용될 수 있으므로 코드만 이전 버전으로 되돌리기 전에 하위 호환성을 확인한다.

