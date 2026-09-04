# 1단계 원본 분석 및 가설 검증

이 폴더는 대화에서 생성한 일본 호텔 검색 원본 296건 분석의 코드·검증 자료·제출물을 한곳에 관리한다. 원본 SQLite는 이 단계 폴더에 복제하지 않고 저장소의 `03_데이터모델링/이전버전/데이터셋/2026-09-03_v02/` 위치에 보존한다.

## 구조

- `scripts/`: 읽기 전용 감사, 마트 구축, 원본 분석, 제출물 생성, 1명령 파이프라인
- `artifacts/`: 체크포인트 감사 JSON
- `local_outputs/20260903_checkpoint1/`: 분석 결정 로그와 품질 점검표
- `local_outputs/20260903_original_296_marts/`: 6개 필수 분석 마트와 검증표
- `local_outputs/20260903_original_296_analysis/`: 직접 재계산한 9개 분석표·Excel·실행 명세
- `local_outputs/submission/`: 제출용 Excel·Word·PNG 6종
- `local_outputs/final_qa_rerun_260903_1420/`: 빈 폴더 재실행 결과와 최종 QA 기록

## 전체 재실행

```powershell
python "1단계_원본_분석_및_가설_검증/scripts/run_original_296_pipeline.py" --db "03_데이터모델링/이전버전/데이터셋/2026-09-03_v02/travel_data_filtered_complete_2026-09-03_v02_비식별.sqlite" --output-dir "1단계_원본_분석_및_가설_검증/local_outputs/rerun_NEW"
```

출력 폴더는 비어 있어야 하며 기존 파일은 덮어쓰지 않는다. 이 단계의 산출물에는 합성·스트레스·1,000명·10,000명 데이터가 없다.
