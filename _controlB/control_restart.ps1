# ==============================================================================
# control_restart.ps1 - Reinicializacao automatica de todo o ecossistema ControlB
# ==============================================================================
# Executa a parada limpa (control_stop.ps1), aguarda 1 segundo e reinicia todos
# os servicos (control_start.ps1), incluindo Postgres, Nginx, Evolution API, Backend e Frontend.
# ==============================================================================

# Caminho absoluto da pasta raiz do projeto (_controlB)
$ProjectRoot = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "[RESTART] Reiniciando Servicos do ControlB" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Define a pasta de trabalho atual como a raiz do projeto
Set-Location $ProjectRoot

# 1. Executa o script de parada para liberar portas e parar containers
& "$ProjectRoot\control_stop.ps1"

# 2. Pausa de 1 segundo para garantir que todas as portas TCP e processos foram liberados no Windows
Start-Sleep -Seconds 1

# 3. Executa o script de inicializacao com o codigo e servicos atualizados
& "$ProjectRoot\control_start.ps1"
