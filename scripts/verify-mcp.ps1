<#
.SYNOPSIS
  Verify configured MCP servers actually start and report tools.
.DESCRIPTION
  Reads the configured MCP servers from ~\.copilot\mcp-config.json, launches each
  with its configured env, sends an MCP `initialize` + `tools/list` over stdio,
  prints the tool count, and terminates. Skips servers that are not configured.
#>

param([string]$McpConfigPath = (Join-Path $env:USERPROFILE '.copilot\mcp-config.json'))

$ErrorActionPreference = 'Continue'

if (-not (Test-Path $McpConfigPath)) {
    Write-Host "No MCP config at $McpConfigPath — run install.ps1 first." -ForegroundColor Red
    exit 1
}

$cfg = Get-Content $McpConfigPath -Raw | ConvertFrom-Json
$names = @('yahoo-finance','sec-edgar','fred') | Where-Object { $cfg.mcpServers.PSObject.Properties.Name -contains $_ }
if (-not $names) {
    Write-Host "None of the trader-agent MCPs are configured yet." -ForegroundColor Yellow
    exit 0
}

# Minimal MCP handshake: initialize then tools/list
$initJson = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify-mcp","version":"0.1"}}}'
$listJson = '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

foreach ($name in $names) {
    $svr = $cfg.mcpServers.$name
    Write-Host "`n[$name] launching: $($svr.command) $($svr.args -join ' ')" -ForegroundColor Cyan
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $svr.command
        foreach ($a in $svr.args) { $psi.ArgumentList.Add($a) | Out-Null }
        if ($svr.env) {
            foreach ($p in $svr.env.PSObject.Properties) { $psi.EnvironmentVariables[$p.Name] = [string]$p.Value }
        }
        $psi.RedirectStandardInput  = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError  = $true
        $psi.UseShellExecute = $false
        $p = [System.Diagnostics.Process]::Start($psi)

        $p.StandardInput.WriteLine($initJson)
        $p.StandardInput.WriteLine($listJson)
        $p.StandardInput.Flush()

        $deadline = (Get-Date).AddSeconds(20)
        $toolsCount = $null
        while ((Get-Date) -lt $deadline -and $null -eq $toolsCount) {
            if ($p.StandardOutput.Peek() -ge 0) {
                $line = $p.StandardOutput.ReadLine()
                if ($line -match '"tools"\s*:\s*\[') {
                    $matches2 = ([regex]::Matches($line, '"name"\s*:\s*"'))
                    $toolsCount = $matches2.Count
                }
            } else { Start-Sleep -Milliseconds 200 }
        }

        if ($toolsCount) {
            Write-Host "[$name] OK — $toolsCount tools exposed" -ForegroundColor Green
        } else {
            Write-Host "[$name] no tools/list response within 20s" -ForegroundColor Yellow
            $err = $p.StandardError.ReadToEnd()
            if ($err) { Write-Host "stderr:`n$err" -ForegroundColor Red }
        }
        if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    } catch {
        Write-Host "[$name] FAILED: $_" -ForegroundColor Red
    }
}
Write-Host "`nDone." -ForegroundColor Cyan
