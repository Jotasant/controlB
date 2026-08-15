# ==============================================================================
# control_stop.ps1 - Encerramento limpo e ordenado do ecossistema ControlB
# ==============================================================================
# Ordem de encerramento:
# 1. Localiza os processos ouvindo nas portas 8000 (Backend) e 9090 (Frontend).
# 2. Localiza processos Python (Uvicorn / HTTP Server) e SASS Watcher por linha de comando.
# 3. Forca o encerramento em arvore (taskkill /F /T) matando processos pais e filhos.
# 4. Desliga o container Nginx Proxy.
# 5. Desliga o container PostgreSQL (preservando o volume de dados .pg_data).
# ==============================================================================

# Caminho absoluto da pasta raiz do projeto (_controlB)
$ProjectRoot = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "[STOP] Encerrando Servicos do ControlB" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# ------------------------------------------------------------------------------
# 1. LOCALIZAR E ENCERRA PROCESSOS PYTHON E SASS WATCHER
# ------------------------------------------------------------------------------
Write-Host "`n1. Parando servidores Python e SASS Watcher..." -ForegroundColor Yellow

$targetPorts = @(8000, 9090)
$pidsToKill = @()

# 1a. Consulta de rede: Encontra os PIDs de processos escutando nas portas 8000 e 9090
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

# 1b. Consulta WMI/CIM: Busca processos por padrao de linha de comando
$cmdProcesses = Get-CimInstance Win32_Process | Where-Object { 
    $_.CommandLine -like "*uvicorn*" -or 
    $_.CommandLine -like "*http.server 9090*" -or
    $_.CommandLine -like "*http.server*" -or
    $_.CommandLine -like "*sass*--watch*" -or
    $_.CommandLine -like "*sass*scss:css*"
}

if ($cmdProcesses) {
    foreach ($proc in $cmdProcesses) {
        if ($pidsToKill -notcontains $proc.ProcessId) {
            $pidsToKill += $proc.ProcessId
        }
    }
}

# 1c. Executa o taskkill /F /T para forcar encerramento da arvore de processos
if ($pidsToKill.Count -gt 0) {
    foreach ($pidToKill in $pidsToKill) {
        Write-Host "  -> Encerrando arvore de processos PID $pidToKill..." -ForegroundColor Red
        & taskkill /F /T /PID $pidToKill 2>$null | Out-Null
    }
    Write-Host "[OK] Servidores Backend (8000), Frontend (9090) e SASS Watcher encerrados totalmente." -ForegroundColor Green
}
else {
    Write-Host "[INFO] Nenhum servidor Uvicorn, Frontend ou SASS em execucao encontrado." -ForegroundColor Gray
}

# ------------------------------------------------------------------------------
# 2. ENCERRAR CONTAINERS DOCKER (NGINX E POSTGRESQL)
# ------------------------------------------------------------------------------
Write-Host "`n2. Parando containers Docker..." -ForegroundColor Yellow
Set-Location $ProjectRoot

# Para o container nginx-proxy se estiver ativo
$nginxStatus = docker inspect --format='{{.State.Running}}' nginx-proxy 2>$null
if ($nginxStatus -eq 'true') {
    Write-Host "  -> Parando container nginx-proxy..." -ForegroundColor Yellow
    docker stop nginx-proxy | Out-Null
    Write-Host "[OK] Container nginx-proxy parado." -ForegroundColor Green
}

# Para os containers do Docker Compose (controlb-postgres)
docker compose stop

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Containers Docker parados com sucesso." -ForegroundColor Green
}
else {
    Write-Host "[ERRO] Erro ao parar os containers Docker." -ForegroundColor Red
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "[FIM] Todos os servicos foram encerrados de forma ordenada!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
