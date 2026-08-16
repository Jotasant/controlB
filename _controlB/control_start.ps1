# ==============================================================================
# control_start.ps1 - Inicializacao completa do ecossistema ControlB
# ==============================================================================
# 1. Sobe containers Docker (PostgreSQL e Nginx Proxy).
# 2. Aguarda o PostgreSQL inicializar.
# 3. Executa migracoes do Alembic.
# 4. Inicia o servidor Backend FastAPI (Uvicorn porta 8000).
# 5. Inicia o servidor Frontend React + Vite (porta 9090 com HMR instantaneo).
# ==============================================================================

$ProjectRoot = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "[START] Iniciando Servicos do ControlB" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ------------------------------------------------------------------------------
# 1. VERIFICAR E INICIAR DOCKER DESKTOP (SE NECESSARIO)
# ------------------------------------------------------------------------------
Write-Host "`n1. Verificando servico do Docker..." -ForegroundColor Yellow

$dockerReady = $false
docker info > $null 2>&1
if ($LASTEXITCODE -eq 0) {
    $dockerReady = $true
    Write-Host "[OK] Docker Engine ja esta em execucao." -ForegroundColor Green
}
else {
    Write-Host "[INFO] Docker Engine nao esta ativo. Tentando iniciar o Docker Desktop..." -ForegroundColor Yellow

    $dockerPaths = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:ProgramW6432\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Programs\Docker\Docker Desktop.exe"
    )

    $dockerExe = $dockerPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($dockerExe) {
        Write-Host "  -> Inicializando: $dockerExe" -ForegroundColor Gray
        Start-Process "$dockerExe"
        Write-Host "[WAIT] Aguardando o Docker Desktop inicializar o motor (pode levar alguns segundos)..." -ForegroundColor Yellow

        $timeoutSeconds = 90
        $elapsed = 0
        $interval = 3

        while ($elapsed -lt $timeoutSeconds) {
            Start-Sleep -Seconds $interval
            $elapsed += $interval

            docker info > $null 2>&1
            if ($LASTEXITCODE -eq 0) {
                $dockerReady = $true
                break
            }
            Write-Host "  -> Aguardando Docker Engine ($elapsed s / $timeoutSeconds s)..." -ForegroundColor Gray
        }
    }
    else {
        Write-Host "[ERRO] Nao foi possivel encontrar o executavel do Docker Desktop." -ForegroundColor Red
    }
}

if (-not $dockerReady) {
    Write-Host "[ERRO] Docker nao respondeu dentro do tempo limite. Abra o Docker Desktop manualmente e tente novamente." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Docker Engine operacional!" -ForegroundColor Green

# ------------------------------------------------------------------------------
# 2. SUBIR CONTAINERS DOCKER (POSTGRESQL E NGINX)
# ------------------------------------------------------------------------------
Write-Host "`n2. Subindo containers do Docker (PostgreSQL e Nginx)..." -ForegroundColor Yellow
Set-Location $ProjectRoot
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERRO] Erro ao subir os containers Docker Compose." -ForegroundColor Red
    exit 1
}

$nginxStatus = docker inspect --format='{{.State.Running}}' nginx-proxy 2>$null
if ($nginxStatus -eq 'true') {
    Write-Host "[OK] Container nginx-proxy ja esta em execucao." -ForegroundColor Green
}
elseif ($nginxStatus -eq 'false') {
    Write-Host "[INFO] Iniciando container nginx-proxy..." -ForegroundColor Yellow
    docker start nginx-proxy | Out-Null
}
else {
    Write-Host "[INFO] Criando e iniciando container nginx-proxy..." -ForegroundColor Yellow
    $NginxConfigPath = Join-Path (Split-Path $ProjectRoot -Parent) "nginx\nginx.conf"
    docker run -d --name nginx-proxy -p 80:80 -v "${NginxConfigPath}:/etc/nginx/nginx.conf:ro" nginx | Out-Null
}

# ------------------------------------------------------------------------------
# 3. AGUARDAR O POSTGRESQL ESTAR PRONTO
# ------------------------------------------------------------------------------
Write-Host "`n3. Aguardando PostgreSQL inicializar..." -ForegroundColor Yellow
$maxTries = 15
$tries = 0
$dbReady = $false

while ($tries -lt $maxTries) {
    $health = docker inspect --format='{{json .State.Health.Status}}' controlb-postgres 2>$null
    if ($health -eq '"healthy"') {
        $dbReady = $true
        break
    }
    Start-Sleep -Seconds 1
    $tries++
}

if ($dbReady) {
    Write-Host "[OK] PostgreSQL pronto para conexoes!" -ForegroundColor Green
}
else {
    Write-Host "[WARN] PostgreSQL ainda esta inicializando, prosseguindo..." -ForegroundColor Yellow
}

# ------------------------------------------------------------------------------
# 4. APLICAR MIGRACOES DO BANCO DE DADOS (ALEMBIC)
# ------------------------------------------------------------------------------
if (Test-Path "$ProjectRoot\.venv\Scripts\python.exe") {
    Write-Host "`n4. Aplicando migracoes do banco de dados (Alembic)..." -ForegroundColor Yellow
    & "$ProjectRoot\.venv\Scripts\python.exe" -m alembic upgrade head
}

# ------------------------------------------------------------------------------
# 5. INICIAR O SERVIDOR BACKEND FASTAPI (UVICORN)
# ------------------------------------------------------------------------------
Write-Host "`n5. Iniciando servidor Backend FastAPI (Uvicorn)..." -ForegroundColor Yellow
$uvicornCmd = "cd '$ProjectRoot'; & '$ProjectRoot\.venv\Scripts\python.exe' -m uvicorn controlb.main:app --app-dir src --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$uvicornCmd" -WindowStyle Normal


# ------------------------------------------------------------------------------
# 6. INICIAR O SERVIDOR FRONTEND (REACT + VITE)
# ------------------------------------------------------------------------------
Write-Host "`n6. Iniciando servidor Frontend React + Vite (Porta 9090)..." -ForegroundColor Yellow
$frontendCmd = "cd '$ProjectRoot\frontend'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$frontendCmd" -WindowStyle Normal

# ------------------------------------------------------------------------------
# PAINEL FINAL DE URLs
# ------------------------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "[SUCCESS] Todos os servicos foram iniciados!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "-> Acesso Principal: http://localhost (Nginx Porta 80)" -ForegroundColor Cyan
Write-Host "-> Frontend Vite:    http://localhost:9090 (HMR Ativo)" -ForegroundColor Cyan
Write-Host "-> Backend API:      http://localhost:8000" -ForegroundColor Cyan
Write-Host "-> Swagger Docs:     http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "-> PostgreSQL:       localhost:5433 (controlb)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Green
Write-Host "Dica: Para parar todos os servicos, execute: .\control_stop" -ForegroundColor Yellow
