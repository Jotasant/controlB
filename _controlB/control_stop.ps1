# ==============================================================================
# control_stop.ps1 - Encerramento limpo e ordenado do ecossistema ControlB
# ==============================================================================
# 1. Encerra processos nas portas 8000 (Backend) e 9090 (Frontend Vite).
# 2. Encerra processos Python/Node remanescentes por padrao de linha de comando.
# 3. Para os containers Nginx e PostgreSQL.
# ==============================================================================

$ProjectRoot = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "[STOP] Encerrando Servicos do ControlB" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# ------------------------------------------------------------------------------
# 1. LOCALIZAR E ENCERRAR PROCESSOS DO BACKEND E FRONTEND
# ------------------------------------------------------------------------------
Write-Host "`n1. Parando servidores Backend (FastAPI) e Frontend (Vite)..." -ForegroundColor Yellow

$targetPorts = @(8000, 9090)
$pidsToKill = @()

# 1a. Busca por conexao TCP ativa nas portas 8000 e 9090
foreach ($port in $targetPorts) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conns) {
        foreach ($conn in $conns) {
            if ($conn.OwningProcess -and $conn.OwningProcess -ne 0 -and $pidsToKill -notcontains $conn.OwningProcess) {
                $pidsToKill += $conn.OwningProcess
            }
        }
    }
}

# 1b. Busca WMI por padrao de comando (Uvicorn / Vite)
$cmdProcesses = Get-CimInstance Win32_Process | Where-Object { 
    $_.CommandLine -like "*uvicorn*" -or 
    $_.CommandLine -like "*vite*" -or
    $_.CommandLine -like "*http.server 9090*"
}

if ($cmdProcesses) {
    foreach ($proc in $cmdProcesses) {
        if ($pidsToKill -notcontains $proc.ProcessId) {
            $pidsToKill += $proc.ProcessId
        }
    }
}

# 1c. Mata os processos e toda a arvore de filhos
if ($pidsToKill.Count -gt 0) {
    foreach ($pidToKill in $pidsToKill) {
        Write-Host "  -> Encerrando arvore de processos PID $pidToKill..." -ForegroundColor Red
        & taskkill /F /T /PID $pidToKill 2>$null | Out-Null
    }
    Write-Host "[OK] Servidores Backend (8000) e Frontend Vite (9090) encerrados." -ForegroundColor Green
}
else {
    Write-Host "[INFO] Nenhum processo nas portas 8000 ou 9090 em execucao." -ForegroundColor Gray
}

# ------------------------------------------------------------------------------
# 2. ENCERRAR CONTAINERS DOCKER
# ------------------------------------------------------------------------------
Write-Host "`n2. Parando containers Docker..." -ForegroundColor Yellow
Set-Location $ProjectRoot

docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Docker Desktop nao esta em execucao. Containers ja estao inativos." -ForegroundColor Gray
}
else {
    # Para o container do Nginx Proxy
    $nginxStatus = docker inspect --format='{{.State.Running}}' nginx-proxy 2>$null
    if ($nginxStatus -eq 'true') {
        Write-Host "  -> Parando container nginx-proxy..." -ForegroundColor Yellow
        docker stop nginx-proxy | Out-Null
        Write-Host "[OK] Container nginx-proxy parado." -ForegroundColor Green
    }

    # Para os containers do Docker Compose (PostgreSQL)
    docker compose stop

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Containers Docker parados com sucesso." -ForegroundColor Green
    }
    else {
        Write-Host "[ERRO] Erro ao parar os containers Docker." -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "[FIM] Todos os servicos foram encerrados de forma ordenada!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
