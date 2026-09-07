$ErrorActionPreference = 'Stop'
$stageRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$categoryNames = @(
    '01_증강_계획과_방법',
    '02_증강_데이터',
    '03_분석_계획과_방법',
    '04_최종_보고서',
    '05_권위자료_원본입력',
    '06_검증_QA_승인',
    '07_개발_테스트',
    '08_실행이력_중간산출물'
)

function Get-Category([string]$name) {
    if ($name -like '호텔검색_3단계증강및AB분석종합보고서_*' -or
        $name -like '~$검색_3단계증강및AB분석종합보고서_*' -or
        $name -like '호텔검색_3단계종합보고서_*') { return '04_최종_보고서' }
    if ($name -eq '호텔검색_1만명증강_탐색용생성_260907_1544_01') { return '02_증강_데이터' }
    if ($name -like '01_*' -or $name -like '*세그먼트AB재설계*') { return '03_분석_계획과_방법' }
    if ($name -like '02_generator*' -or $name -like '02_base_config*' -or
        $name -like '02_config_schema*' -or $name -like '02_schema*' -or
        $name -like '02_calibration*' -or $name -like '02_data_dictionary*' -or
        $name -like '*1000명_10000명*증강계획서*') { return '01_증강_계획과_방법' }
    if ($name -eq 'travel_data_filtered_complete_2026-09-03_v03_비식별.sqlite' -or
        $name -like 'BI시각화_*' -or $name -like '호텔검색_32일차*') { return '05_권위자료_원본입력' }
    if ($name -like '00_*' -or $name -like '02_*report*' -or
        $name -like '02_*manifest*' -or $name -like '02_*audit*' -or
        $name -like '02_*results*' -or $name -like '02_*gate*' -or
        $name -like '02_reference1000*' -or $name -like '02_clone*' -or
        $name -like '02_prod*' -or $name -like '02_step*' -or
        $name -like '*품질판정보고서*' -or $name -like '*테스트결과*') { return '06_검증_QA_승인' }
    if ($name -like '02_tests*' -or $name -eq '02_clone_qa_seed_dbs_v01' -or
        $name -eq '__pycache__' -or $name -like '02_dryrun*' -or
        $name -like '*생성시스템개발*' -or $name -like '*생성시스템개정*') { return '07_개발_테스트' }
    if ($name -like '*기준선재수립*' -or $name -like '*검증체인통합*' -or
        $name -like '*다중시드교정*' -or $name -like '*승인인터페이스*' -or
        $name -like '*결합전이개정및검증*') { return '08_실행이력_중간산출물' }
    throw "분류되지 않은 항목: $name"
}

foreach ($category in $categoryNames) {
    $categoryPath = Join-Path $stageRoot $category
    if (-not (Test-Path -LiteralPath $categoryPath)) {
        New-Item -ItemType Directory -Path $categoryPath | Out-Null
    }
}
foreach ($sub in @('현재본', '이전버전', '내부작업')) {
    $subPath = Join-Path (Join-Path $stageRoot '04_최종_보고서') $sub
    if (-not (Test-Path -LiteralPath $subPath)) { New-Item -ItemType Directory -Path $subPath | Out-Null }
}

$sourceItems = Get-ChildItem -LiteralPath $stageRoot -Force | Where-Object {
    $_.Name -notin $categoryNames -and $_.Name -ne '99_정리_인덱스'
}
$plan = [System.Collections.Generic.List[object]]::new()
foreach ($item in $sourceItems) {
    $category = Get-Category $item.Name
    $relativeTarget = $category
    if ($category -eq '04_최종_보고서') {
        if ($item.Name -eq '호텔검색_3단계증강및AB분석종합보고서_260907_1720_01.docx') {
            $relativeTarget = Join-Path $category '현재본'
        } elseif ($item.Name -like '호텔검색_3단계증강및AB분석종합보고서_*.docx' -or $item.Name -like '~$검색_3단계증강및AB분석종합보고서_*.docx') {
            $relativeTarget = Join-Path $category '이전버전'
        } else {
            $relativeTarget = Join-Path $category '내부작업'
        }
    }
    $targetDirectory = Join-Path $stageRoot $relativeTarget
    $targetPath = Join-Path $targetDirectory $item.Name
    if (-not $targetPath.StartsWith($stageRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "대상 경로가 작업 폴더 밖입니다: $targetPath"
    }
    $targetExists = Test-Path -LiteralPath $targetPath
    $locked = $false
    $files = if ($item.PSIsContainer) { Get-ChildItem -LiteralPath $item.FullName -Recurse -File -Force } else { @($item) }
    foreach ($candidateFile in @($files)) {
        try {
            $stream = [IO.File]::Open($candidateFile.FullName, 'Open', 'ReadWrite', 'None')
            $stream.Close()
        } catch {
            $locked = $true
            break
        }
    }
    $plan.Add([pscustomobject]@{
        item_name = $item.Name
        item_type = if ($item.PSIsContainer) { 'directory' } else { 'file' }
        category = $category
        source_path = $item.FullName
        target_path = $targetPath
        file_count = @($files).Count
        bytes = (@($files) | Measure-Object Length -Sum).Sum
        status = if ($targetExists) { 'HOLD_PARTIAL_TARGET' } elseif ($locked) { 'HOLD_LOCKED' } else { 'PLANNED' }
    })
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$planPath = Join-Path $PSScriptRoot "stage3_reorganization_plan_$timestamp.csv"
$plan | Export-Csv -LiteralPath $planPath -NoTypeInformation -Encoding UTF8

foreach ($entry in $plan) {
    if ($entry.status -ne 'PLANNED') { continue }
    Move-Item -LiteralPath $entry.source_path -Destination $entry.target_path
    $entry.status = 'MOVED'
}

$plan | Export-Csv -LiteralPath $planPath -NoTypeInformation -Encoding UTF8
$remaining = Get-ChildItem -LiteralPath $stageRoot -Force | Where-Object {
    $_.Name -notin $categoryNames -and $_.Name -ne '99_정리_인덱스'
} | Select-Object Name, FullName, Length, Mode
$summary = [ordered]@{
    executed_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
    stage_root = $stageRoot
    moved_top_level_items = @($plan | Where-Object status -eq 'MOVED').Count
    held_items = @($plan | Where-Object status -like 'HOLD*').Count
    moved_file_count = ($plan | Where-Object status -eq 'MOVED' | Measure-Object file_count -Sum).Sum
    moved_bytes = ($plan | Where-Object status -eq 'MOVED' | Measure-Object bytes -Sum).Sum
    remaining_unclassified_top_level = @($remaining)
    categories = @($categoryNames | ForEach-Object {
        $path = Join-Path $stageRoot $_
        $files = Get-ChildItem -LiteralPath $path -Recurse -File -Force
        [ordered]@{ name = $_; path = $path; files = @($files).Count; bytes = ($files | Measure-Object Length -Sum).Sum }
    })
    plan_csv = $planPath
}
$summaryPath = Join-Path $PSScriptRoot "stage3_reorganization_summary_$timestamp.json"
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
$summary | ConvertTo-Json -Depth 6



