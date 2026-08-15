# ==============================================================================
# control_start.ps1 - Inicializacao completa do ecossistema ControlB
# ==============================================================================
# Ordem de execucao:
# 1. Sobe os containers Docker (PostgreSQL no Compose e Nginx Proxy).
# 2. Aguarda o PostgreSQL estar 100% pronto (healthcheck 'healthy').
# 3. Executa as migracoes pendentes do banco de dados (Alembic).
# 4. Compila o SCSS e inicia o SASS Watcher em segundo plano.
# 5. Inicia o servidor Backend FastAPI (Uvicorn com --reload na porta 8000).
# 6. Inicia o servidor estatico Frontend (HTTP Server na porta 9090).
# ==============================================================================

# Variavel com o caminho absoluto da pasta raiz do projeto (_controlB)
$ProjectRoot = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "[START] Iniciando Servicos do ControlB" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ------------------------------------------------------------------------------
# 1. VERIFICAR E INICIAR CONTAINERS DOCKER
# ------------------------------------------------------------------------------
Write-Host "`n1. Subindo containers do Docker (PostgreSQL e Nginx)..." -ForegroundColor Yellow
Set-Location $ProjectRoot
docker compose up -d

# Verifica se o Docker falhou (ex: Docker Desktop fechado)
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERRO] Erro ao subir os containers Docker. Verifique se o Docker Desktop esta ativo." -ForegroundColor Red
    exit 1
}

# Gerenciamento do container do proxy reverso Nginx
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
# 2. AGUARDAR O POSTGRESQL ESTAR PRONTO (HEALTHCHECK)
# ------------------------------------------------------------------------------
Write-Host "[WAIT] Aguardando PostgreSQL inicializar..." -ForegroundColor Yellow
$maxTries = 15
$tries = 0
$dbReady = $false

# Loop que consulta a saude do container a cada 1 segundo (ate 15 segundos)
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
# 3. APLICAR MIGRACOES DO BANCO DE DADOS (ALEMBIC)
# ------------------------------------------------------------------------------
if (Test-Path "$ProjectRoot\.venv\Scripts\python.exe") {
    Write-Host "`n2. Aplicando migracoes do banco de dados (Alembic)..." -ForegroundColor Yellow
    & "$ProjectRoot\.venv\Scripts\python.exe" -m alembic upgrade head
}

# ------------------------------------------------------------------------------
# 4. COMPILAR SCSS E INICIAR O SASS WATCHER
# ------------------------------------------------------------------------------
Write-Host "`n3. Compilando SCSS para CSS e iniciando Watcher..." -ForegroundColor Yellow
Set-Location "$ProjectRoot\frontend"
npx --yes sass scss:css --no-source-map
$sassCmd = "cd '$ProjectRoot\frontend'; npx sass scss:css --watch --no-source-map"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$sassCmd" -WindowStyle Normal

# ------------------------------------------------------------------------------
# 5. INICIAR O SERVIDOR BACKEND FASTAPI (UVICORN)
# ------------------------------------------------------------------------------
Write-Host "`n4. Iniciando servidor Backend FastAPI (Uvicorn)..." -ForegroundColor Yellow
$uvicornCmd = "cd '$ProjectRoot'; .\.venv\Scripts\Activate.ps1; python -m uvicorn controlb.main:app --app-dir src --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$uvicornCmd" -WindowStyle Normal

# ------------------------------------------------------------------------------
# 6. INICIAR O SERVIDOR FRONTEND (HTTP SERVER)
# ------------------------------------------------------------------------------
Write-Host "`n5. Iniciando servidor Frontend (Porta 9090)..." -ForegroundColor Yellow
$frontendCmd = "cd '$ProjectRoot'; .\.venv\Scripts\Activate.ps1; python -m http.server 9090 --directory frontend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "$frontendCmd" -WindowStyle Normal

# ------------------------------------------------------------------------------
# PAINEL FINAL DE URLs
# ------------------------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "[SUCCESS] Todos os servicos foram iniciados!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "-> Nginx Proxy:  http://localhost (Porta 80)" -ForegroundColor Cyan
Write-Host "-> Frontend:     http://localhost:9090" -ForegroundColor Cyan
Write-Host "-> Backend API:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "-> Swagger Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "-> PostgreSQL:   localhost:5433 (controlb)" -ForegroundColor Cyan
Write-Host "-> SASS Watcher: Ativo (Compila SCSS -> CSS automaticamente)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Green
Write-Host "Dica: Para parar todos os servicos em ordem, execute: .\control_stop" -ForegroundColor Yellow
