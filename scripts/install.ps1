<#
.SYNOPSIS
  One-time installer for trader-agent.
.DESCRIPTION
  - Prompts for account / risk parameters
  - Renders agent/risk-rules.template.md into the private data folder
  - Initializes a SQLite trade database from schema/init.sql
  - Copies the agent definition into ~\.copilot\agents\
  - Registers MCP servers in ~\.copilot\mcp-config.json (with confirmation)
.NOTES
  Personal data NEVER goes into this repo. Default private folder: ..\trader-agent-private\
#>

[CmdletBinding()]
param(
    [string]$PrivateDir = (Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) 'trader-agent-private'),
    [string]$CopilotAgentsDir = (Join-Path $env:USERPROFILE '.copilot\agents'),
    [string]$McpConfigPath = (Join-Path $env:USERPROFILE '.copilot\mcp-config.json'),
    [switch]$SkipMcpRegister
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent

function Read-Default($prompt, $default) {
    $v = Read-Host "$prompt [$default]"
    if ([string]::IsNullOrWhiteSpace($v)) { return $default } else { return $v }
}

Write-Host "`n=== trader-agent install ===" -ForegroundColor Cyan
Write-Host "Repo:           $RepoRoot"
Write-Host "Private data:   $PrivateDir"
Write-Host "Agent install:  $CopilotAgentsDir"
Write-Host ""

# --- Prompts ---
$accountSize       = [double](Read-Default "Account size (USD)" "20000")
$riskPct           = [double](Read-Default "Risk per trade (%)" "1.5")
$maxHeatPct        = [double](Read-Default "Max portfolio heat (%)" "6")
$maxOpenPositions  = [int](Read-Default "Max concurrent open positions" "5")
$sectors           = Read-Default "Sectors of focus" "Tech (broad)"
$instruments       = Read-Default "Instruments" "Stocks + Options"
$horizons          = Read-Default "Horizons" "Swing, Position"

$maxRiskUsd = [math]::Round($accountSize * $riskPct / 100, 2)
$maxHeatUsd = [math]::Round($accountSize * $maxHeatPct / 100, 2)

# --- Create private folder ---
New-Item -ItemType Directory -Force -Path $PrivateDir, (Join-Path $PrivateDir 'notes') | Out-Null

# --- Render risk-rules.md ---
$template = Get-Content (Join-Path $RepoRoot 'agent\risk-rules.template.md') -Raw
$rendered = $template `
    -replace '\{\{ACCOUNT_SIZE_USD\}\}',    $accountSize `
    -replace '\{\{RISK_PCT_PER_TRADE\}\}',  $riskPct `
    -replace '\{\{MAX_HEAT_PCT\}\}',        $maxHeatPct `
    -replace '\{\{MAX_RISK_USD\}\}',        $maxRiskUsd `
    -replace '\{\{MAX_HEAT_USD\}\}',        $maxHeatUsd `
    -replace '\{\{MAX_OPEN_POSITIONS\}\}',  $maxOpenPositions `
    -replace '\{\{SECTORS\}\}',             $sectors `
    -replace '\{\{INSTRUMENTS\}\}',         $instruments `
    -replace '\{\{HORIZONS\}\}',            $horizons

$rulesPath = Join-Path $PrivateDir 'risk-rules.md'
Set-Content -Path $rulesPath -Value $rendered -Encoding UTF8
Write-Host "Wrote $rulesPath" -ForegroundColor Green

# --- Empty personal files ---
$doNotTradePath = Join-Path $PrivateDir 'do-not-trade.txt'
if (-not (Test-Path $doNotTradePath)) {
    Set-Content -Path $doNotTradePath -Value "# One ticker per line. Lines starting with # are ignored.`n" -Encoding UTF8
    Write-Host "Wrote $doNotTradePath"
}

$accountStatePath = Join-Path $PrivateDir 'account-state.json'
if (-not (Test-Path $accountStatePath)) {
    @{
        account_size_usd     = $accountSize
        max_risk_usd         = $maxRiskUsd
        max_heat_usd         = $maxHeatUsd
        max_open_positions   = $maxOpenPositions
        current_open_risk    = 0
        updated_at           = (Get-Date).ToString('o')
    } | ConvertTo-Json | Set-Content -Path $accountStatePath -Encoding UTF8
    Write-Host "Wrote $accountStatePath"
}

# --- Initialize SQLite DB ---
$dbPath = Join-Path $PrivateDir 'trade-data.db'
$sqlPath = Join-Path $RepoRoot 'schema\init.sql'

$sqlite = Get-Command sqlite3 -ErrorAction SilentlyContinue
if ($sqlite) {
    Get-Content $sqlPath -Raw | & sqlite3.exe $dbPath
    Write-Host "Initialized SQLite DB at $dbPath (via sqlite3.exe)" -ForegroundColor Green
} else {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if ($py) {
        $script = @"
import sqlite3, sys
con = sqlite3.connect(r'$dbPath')
with open(r'$sqlPath', 'r', encoding='utf-8') as f:
    con.executescript(f.read())
con.commit()
con.close()
print('DB initialized')
"@
        $script | & python -
        Write-Host "Initialized SQLite DB at $dbPath (via python sqlite3)" -ForegroundColor Green
    } else {
        Write-Warning "Neither sqlite3 nor python found. Run schema/init.sql manually against $dbPath."
    }
}

# --- Install agent file with LOCAL_DATA_PATH substituted ---
$agentSrc = Join-Path $RepoRoot 'agent\trader.agent.md'
$agentContent = Get-Content $agentSrc -Raw
$agentContent = $agentContent -replace '\{LOCAL_DATA_PATH\}', ($PrivateDir -replace '\\','\\')

New-Item -ItemType Directory -Force -Path $CopilotAgentsDir | Out-Null
$agentDest = Join-Path $CopilotAgentsDir 'trader.agent.md'
Set-Content -Path $agentDest -Value $agentContent -Encoding UTF8
Write-Host "Installed agent to $agentDest" -ForegroundColor Green

# --- MCP server registration (opt-in) ---
if (-not $SkipMcpRegister) {
    Write-Host "`nMCP server registration"
    Write-Host "Will add: mcp-yahoo-finance, sec-edgar-mcp, mcp-fred to $McpConfigPath"
    $confirm = Read-Default "Proceed? (y/N)" "N"
    if ($confirm -match '^[yY]') {
        $secUserAgent = Read-Default "SEC EDGAR User-Agent (your name + email, required)" "Your Name (you@example.com)"
        $fredKey = Read-Default "FRED API key (leave blank to skip mcp-fred)" ""
        $fredDir = Join-Path $PrivateDir 'fred-data'

        # Initialize or back up the config
        if (Test-Path $McpConfigPath) {
            Copy-Item $McpConfigPath "$McpConfigPath.bak.$(Get-Date -Format yyyyMMddHHmmss)" -Force
            $cfg = Get-Content $McpConfigPath -Raw | ConvertFrom-Json
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path $McpConfigPath -Parent) | Out-Null
            $cfg = [PSCustomObject]@{ mcpServers = [PSCustomObject]@{} }
        }
        if (-not $cfg.mcpServers) { $cfg | Add-Member -NotePropertyName mcpServers -NotePropertyValue (New-Object PSObject) }

        $cfg.mcpServers | Add-Member -Force -NotePropertyName 'yahoo-finance' -NotePropertyValue ([PSCustomObject]@{
            type    = 'stdio'
            command = 'uvx'
            args    = @('mcp-yahoo-finance')
        })

        $cfg.mcpServers | Add-Member -Force -NotePropertyName 'sec-edgar' -NotePropertyValue ([PSCustomObject]@{
            type    = 'stdio'
            command = 'uvx'
            args    = @('--from', 'git+https://github.com/stefanoamorelli/sec-edgar-mcp.git', 'sec-edgar-mcp')
            env     = @{ SEC_EDGAR_USER_AGENT = $secUserAgent }
        })

        if ($fredKey) {
            New-Item -ItemType Directory -Force -Path $fredDir | Out-Null
            # Use module entry-point form to avoid console-script naming issues
            $cfg.mcpServers | Add-Member -Force -NotePropertyName 'fred' -NotePropertyValue ([PSCustomObject]@{
                type    = 'stdio'
                command = 'uvx'
                args    = @('--from', 'mcp-fred', 'python', '-m', 'mcp_fred')
                env     = @{
                    FRED_API_KEY     = $fredKey
                    FRED_STORAGE_DIR = $fredDir
                }
            })
        }

        $cfg | ConvertTo-Json -Depth 10 | Set-Content -Path $McpConfigPath -Encoding UTF8
        Write-Host "Updated $McpConfigPath" -ForegroundColor Green
    } else {
        Write-Host "Skipped MCP registration. You can run this script again with confirmation, or edit $McpConfigPath manually." -ForegroundColor Yellow
    }
}

Write-Host "`n=== Done ===" -ForegroundColor Cyan
Write-Host "Next steps:"
Write-Host "  1. Restart Copilot CLI so it picks up the new agent and MCP config"
Write-Host "  2. Run: .\scripts\verify-mcp.ps1"
Write-Host "  3. Try: @trader research <TICKER>"
