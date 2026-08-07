#Requires -Version 5.1
<#
.SYNOPSIS
    Prepara o ambiente do hermes-voice no Windows.

.DESCRIPTION
    Cria o venv, instala dependencias, baixa o binario e a voz pt-BR do Piper e
    imprime as pendencias de EDR. Nao altera nada fora da pasta do projeto e
    nao aplica excecao de seguranca por conta propria.

.PARAMETER SkipPiper
    Nao baixa o binario nem a voz do Piper (use se for so Azure ou --no-tts).

.PARAMETER Cpu
    Configura o Whisper para CPU, evitando a dor de CUDA/cuDNN no Windows.

.EXAMPLE
    .\scripts\setup.ps1
    .\scripts\setup.ps1 -Cpu
#>
[CmdletBinding()]
param(
    [switch]$SkipPiper,
    [switch]$Cpu
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Push-Location $Root

function Write-Step { param([string]$Text) Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Warn { param([string]$Text) Write-Host "    ! $Text" -ForegroundColor Yellow }
function Write-Ok   { param([string]$Text) Write-Host "    + $Text" -ForegroundColor Green }

try {
    # -----------------------------------------------------------------------
    Write-Step 'Verificando Python'
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { throw 'Python nao encontrado no PATH. Instale 3.10-3.12 e reabra o terminal.' }

    $version = (& python -c 'import sys; print("%d.%d" % sys.version_info[:2])').Trim()
    Write-Ok "Python $version em $($py.Source)"
    if ([version]$version -lt [version]'3.10') { throw "Python $version e antigo demais. Use 3.10+." }
    if ([version]$version -ge [version]'3.13') {
        Write-Warn "Python $version: alguns wheels (ctranslate2, pynput) podem nao existir ainda. 3.12 e a aposta segura."
    }

    # -----------------------------------------------------------------------
    Write-Step 'Criando ambiente virtual'
    if (-not (Test-Path '.venv')) {
        & python -m venv .venv
        Write-Ok 'venv criado em .venv'
    } else {
        Write-Ok '.venv ja existe; reutilizando'
    }
    $venvPy = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) { throw "Interpretador do venv nao encontrado em $venvPy" }

    # -----------------------------------------------------------------------
    Write-Step 'Instalando dependencias'
    & $venvPy -m pip install --upgrade pip --quiet
    & $venvPy -m pip install -e ".[wake,ptt,dev]"
    if ($LASTEXITCODE -ne 0) { throw 'pip install falhou. Veja o erro acima.' }
    Write-Ok 'Dependencias instaladas'

    # -----------------------------------------------------------------------
    if (-not $SkipPiper) {
        Write-Step 'Baixando Piper (binario + voz pt-BR)'

        $binDir   = Join-Path $Root 'bin'
        $piperDir = Join-Path $binDir 'piper'
        $voiceDir = Join-Path $Root 'voices'
        New-Item -ItemType Directory -Force -Path $binDir, $voiceDir | Out-Null

        if (-not (Test-Path (Join-Path $piperDir 'piper.exe'))) {
            $zipUrl = 'https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip'
            $zip    = Join-Path $env:TEMP 'piper_windows_amd64.zip'
            Write-Host "    baixando $zipUrl"
            Invoke-WebRequest -Uri $zipUrl -OutFile $zip -UseBasicParsing
            Expand-Archive -Path $zip -DestinationPath $binDir -Force
            Remove-Item $zip -Force
            Write-Ok 'piper.exe instalado em bin\piper\'
        } else {
            Write-Ok 'piper.exe ja presente'
        }

        # Voz masculina pt-BR. Alternativa: .../pt/pt_BR/edresson/low/
        $base = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium'
        foreach ($file in @('pt_BR-faber-medium.onnx', 'pt_BR-faber-medium.onnx.json')) {
            $dest = Join-Path $voiceDir $file
            if (Test-Path $dest) { Write-Ok "$file ja presente"; continue }
            Write-Host "    baixando $file"
            Invoke-WebRequest -Uri "$base/$file" -OutFile $dest -UseBasicParsing
            Write-Ok $file
        }
    }

    # -----------------------------------------------------------------------
    Write-Step 'Configuracao'
    if (-not (Test-Path '.env')) {
        Copy-Item '.env.example' '.env'
        Write-Ok '.env criado a partir do exemplo'
    } else {
        Write-Ok '.env ja existe; nao foi tocado'
    }

    if ($Cpu) {
        $env_content = Get-Content '.env' -Raw
        $env_content = $env_content -replace 'WHISPER_DEVICE=cuda', 'WHISPER_DEVICE=cpu'
        $env_content = $env_content -replace 'WHISPER_COMPUTE=int8_float16', 'WHISPER_COMPUTE=int8'
        Set-Content '.env' $env_content -NoNewline
        Write-Ok 'Whisper configurado para CPU'
    }

    # -----------------------------------------------------------------------
    Write-Step 'Pendencias manuais'

    Write-Host ''
    Write-Host '  1. EDR -- leia antes de rodar' -ForegroundColor White
    Write-Warn 'O componente de maior risco NAO e o microfone: e o hook global'
    Write-Warn 'de teclado do pynput (SetWindowsHookEx), assinatura classica de'
    Write-Warn 'keylogger. Somado a microfone + egress de rede, forma a triade'
    Write-Warn 'comportamental de um implante de spyware. O alerta e esperado.'
    Write-Host ''
    Write-Host '     Saida preferida -- nao precisa de excecao nenhuma:' -ForegroundColor Gray
    Write-Host '       hermes-voice --trigger console' -ForegroundColor Green
    Write-Host '     ENTER inicia e encerra a gravacao. Sem hook global. O unico' -ForegroundColor Gray
    Write-Host '     custo e precisar de foco na janela do console.' -ForegroundColor Gray
    Write-Host ''
    Write-Host '     Se quiser mesmo o push-to-talk, exclusao pelo console de' -ForegroundColor Gray
    Write-Host '     gestao (nunca local): Path, modo Interoperability.' -ForegroundColor Gray
    Write-Host "       Path: $Root" -ForegroundColor Gray
    Write-Host '     Suppress Alerts apenas silencia o alerta; nao impede bloqueio.' -ForegroundColor Gray

    Write-Host ''
    Write-Host '  2. GPU (opcional, mas vale ~5x na latencia do STT)' -ForegroundColor White
    if ($Cpu) {
        Write-Warn 'Configurado para CPU. STT vai levar 1-3 s por turno.'
    } else {
        Write-Warn 'faster-whisper em CUDA no Windows exige cuDNN 9 no PATH.'
        Write-Warn 'O erro tipico e "Could not locate cudnn_ops64_9.dll".'
        Write-Warn 'Se aparecer, ha tres saidas, em ordem de esforco:'
        Write-Host '       a) rode .\scripts\setup.ps1 -Cpu (funciona hoje, mais lento)' -ForegroundColor Gray
        Write-Host '       b) pip install nvidia-cudnn-cu12 nvidia-cublas-cu12 e' -ForegroundColor Gray
        Write-Host '          adicione o site-packages\nvidia\**\bin ao PATH' -ForegroundColor Gray
        Write-Host '       c) rode tudo em WSL2 com passthrough de GPU (mais limpo,' -ForegroundColor Gray
        Write-Host '          mas o audio precisa atravessar para o host)' -ForegroundColor Gray
    }

    Write-Host ''
    Write-Host '  3. HERMES' -ForegroundColor White
    Write-Warn 'Ajuste HERMES_URL e PICOVOICE_ACCESS_KEY no .env.'
    Write-Warn 'compativel com /v1/chat/completions em streaming (SSE).'

    Write-Host ''
    Write-Host '  4. FONE DE OUVIDO' -ForegroundColor White
    Write-Warn 'Na v0 nao ha cancelamento de eco. Com caixas abertas o'
    Write-Warn 'microfone escuta a propria voz do Hermes. Use fone.'

    # -----------------------------------------------------------------------
    Write-Step 'Pronto. Proximos passos'
    Write-Host ''
    Write-Host '    .\.venv\Scripts\Activate.ps1' -ForegroundColor Green
    Write-Host '    hermes-voice --doctor                       # diz o que ainda falta' -ForegroundColor Green
    Write-Host '    hermes-voice --text                         # valide Hermes + voz sem microfone' -ForegroundColor Green
    Write-Host '    hermes-voice --trigger console              # ENTER, sem hook de teclado' -ForegroundColor Green
    Write-Host '    hermes-voice                                # microfone aberto' -ForegroundColor Green
    Write-Host ''
}
catch {
    Write-Host "`nFALHOU: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
