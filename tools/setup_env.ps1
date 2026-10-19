# PaperSeek environment bootstrap (idempotent).
# NOTE: intentionally ASCII-only. Windows PowerShell 5.1 reads UTF-8 files without a
# BOM as ANSI, so non-ASCII text here would corrupt parsing. Chinese docs live in docs/*.md.
# Usage: powershell -ExecutionPolicy Bypass -File tools\setup_env.ps1
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
$rawDir = Join-Path $root 'data\raw'
New-Item -ItemType Directory -Force -Path $logDir, $rawDir | Out-Null
$log = Join-Path $logDir 'setup.log'

function Step([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding utf8
}
function Run([string]$exe, [string[]]$argv, [string]$note) {
    Step "RUN $note"
    $out = & $exe @argv 2>&1
    $code = $LASTEXITCODE
    $out | ForEach-Object { Add-Content -Path $log -Value $_ -Encoding utf8 }
    $out | Select-Object -Last 8 | ForEach-Object { Write-Host "  $_" }
    if ($code -ne 0) { throw "command failed ($code): $exe $($argv -join ' ')" }
    return $out
}

Step 'STEP 1/6 create .venv (inherit system torch/cuda via --system-site-packages)'
$sysPy = (Get-Command python).Source
Step "system python = $sysPy"
$venvDir = Join-Path $root '.venv'
$vpy = Join-Path $venvDir 'Scripts\python.exe'
if (-not (Test-Path $vpy)) {
    & $sysPy -m venv $venvDir --system-site-packages
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
} else {
    Step 'venv already exists, skip creation'
}

Step 'STEP 2/6 install python packages'
Run $vpy @('-m','pip','install','--disable-pip-version-check','-q','--upgrade','pip') 'upgrade pip'
Run $vpy @('-m','pip','install','--disable-pip-version-check','sentence-transformers','PyMuPDF','jieba','rank-bm25','playwright') 'install deps'

Step 'STEP 3/6 download SciFact (BEIR public benchmark: corpus/queries/qrels)'
& $vpy (Join-Path $root 'scripts\download_data.py') 2>&1 | ForEach-Object { Add-Content -Path $log -Value $_ -Encoding utf8; Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) { throw 'SciFact download failed' }

Step 'STEP 4/6 cache SBERT model all-MiniLM-L6-v2 via hf-mirror'
$env:HF_ENDPOINT = 'https://hf-mirror.com'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$code = @'
from huggingface_hub import snapshot_download
p = snapshot_download("sentence-transformers/all-MiniLM-L6-v2")
print("MODEL_DIR=" + p)
'@
$out = & $vpy -c $code 2>&1
$out | ForEach-Object { Add-Content -Path $log -Value $_ -Encoding utf8; Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) { throw 'model download failed' }

Step 'STEP 5/6 environment self-check'
$code2 = @'
import sys, torch, sklearn, numpy, pandas, fitz, jieba, rank_bm25
import sentence_transformers as st
print("python", sys.version.split()[0])
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
print("sklearn", sklearn.__version__, "numpy", numpy.__version__, "pandas", pandas.__version__)
print("sentence-transformers", st.__version__)
print("pymupdf ok, jieba ok, rank_bm25 ok")
'@
$out = & $vpy -c $code2 2>&1
$out | ForEach-Object { Add-Content -Path $log -Value $_ -Encoding utf8; Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) { throw 'self-check failed' }

Step 'STEP 6/6 write environment report'
$out = & $vpy -c 'import sys,platform,torch,sklearn,sentence_transformers as st;print(sys.version.split()[0], platform.platform(), "torch="+torch.__version__, "cuda="+str(torch.cuda.is_available()), "st="+st.__version__)' 2>&1
$out | Add-Content -Path (Join-Path $logDir 'environment_report.txt') -Encoding utf8
Step 'SETUP_DONE'
