<#
.SYNOPSIS
    Deterministic, self-contained tests for trusted-gate.ps1.

    These tests exercise the trusted-runner-only boundaries with a fake `gh`
    executable. The existing gate.Tests.ps1 remains the authoritative suite for
    duplicate, stale, path, and dispatch validation semantics; this suite adds
    the pull_request_target trust-boundary and head-content checks.
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:passed = 0
$script:failed = 0
$scriptRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$scriptUnderTest = Join-Path $scriptRoot 'trusted-gate.ps1'
$repoRoot = Resolve-Path (Join-Path $scriptRoot '..\..')
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("intercraft-trusted-gate-test-{0}" -f [guid]::NewGuid().ToString('N'))

function It {
    param([Parameter(Mandatory)][string] $Name, [Parameter(Mandatory)][scriptblock] $Test)
    try { & $Test; $script:passed++; Write-Host "PASS $Name" }
    catch { $script:failed++; Write-Host "FAIL $Name :: $($_.Exception.Message)" }
}

function Assert-True { param([bool] $Condition, [string] $Message); if (-not $Condition) { throw $Message } }
function Assert-Contains { param([string] $Text, [string] $Pattern, [string] $Message); if ($Text -notmatch $Pattern) { throw "$Message (pattern '$Pattern'; output=$Text)" } }

function New-FakeGh {
    param([Parameter(Mandatory)][string] $Directory)
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $shim = @'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0gh.ps1" %*
exit /b %ERRORLEVEL%
'@
    Set-Content -LiteralPath (Join-Path $Directory 'gh.cmd') -Value $shim -Encoding ASCII
    $fake = @'
param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Arguments)
$joined = $Arguments -join ' '
if ($env:FAKE_GH_FAIL -eq '1') { [Console]::Error.WriteLine('simulated transport failure'); exit 7 }
if ($joined -match '/pulls/42/files') { Get-Content -Raw $env:FAKE_FILES; exit 0 }
if ($joined -match '/pulls/42') { Get-Content -Raw $env:FAKE_PR; exit 0 }
if ($joined -match '/contents/') { Get-Content -Raw $env:FAKE_CONTENT; exit 0 }
if ($joined -match '/git/ref/heads/master') { '{"object":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}'; exit 0 }
'{}'
'@
    Set-Content -LiteralPath (Join-Path $Directory 'gh.ps1') -Value $fake -Encoding UTF8
}

function New-PrJson {
    param([string] $Body = '', [string] $BaseRef = 'master', [string] $HeadRepo = 'Sandape/interCraft', [string] $HeadSha = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb')
    $head = @{ sha = $HeadSha; repo = if ($null -eq $HeadRepo) { $null } else { @{ full_name = $HeadRepo } } }
    $pr = @{ number = 42; state = 'open'; body = $Body; base = @{ ref = $BaseRef; sha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' }; head = $head }
    return ($pr | ConvertTo-Json -Depth 6)
}

function New-ContentJson {
    param([string] $Path = '.github/dispatches/req-100-trusted-gate-20260716-03.json', [string] $Name = 'req-100-trusted-gate-20260716-03.json', [int] $Size = 10, [string] $Type = 'file', [string] $Encoding = 'base64')
    $content = @{ type = $Type; encoding = $Encoding; name = $Name; path = $Path; sha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'; size = $Size; content = 'e30=' }
    return ($content | ConvertTo-Json -Depth 4)
}

function New-ValidContentJson {
    $envelope = [ordered]@{
        dispatch_id = 'req-100-trusted-gate-20260716-03'
        issue_number = 100
        driver = 'codex'
        base_sha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        spec_task_id = 'REQ-100'
        ac_hash = '57c6f066ec9187f9ed998028f31ce2dc5541daa976a03c95a91323c6ba9d1d4b'
        canonical_ac_text_version = 'v1'
        allowed_paths = @('.github/workflows/governance-gate.yml', 'scripts/governance/trusted-gate.ps1', 'scripts/governance/tests/**', 'docs/evidence/governance-gate-trusted-runner-20260716.md', 'docs/engineering/delivery-sop.md', 'docs/decisions/ADR-003-governance-gate-design.md', '.github/dispatches/**')
        governance_version = 'stage-a-owner-pr-bypass-v1'
        created_at = '2026-07-16T10:56:15Z'
        state = 'active'
    }
    $json = $envelope | ConvertTo-Json -Depth 8 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $header = [Text.Encoding]::ASCII.GetBytes("blob $($bytes.Length)`0")
    $payload = New-Object byte[] ($header.Length + $bytes.Length)
    [Array]::Copy($header, 0, $payload, 0, $header.Length); [Array]::Copy($bytes, 0, $payload, $header.Length, $bytes.Length)
    $sha = (([Security.Cryptography.SHA1]::Create().ComputeHash($payload) | ForEach-Object { $_.ToString('x2') }) -join '')
    return (@{ type = 'file'; encoding = 'base64'; name = 'req-100-trusted-gate-20260716-03.json'; path = '.github/dispatches/req-100-trusted-gate-20260716-03.json'; sha = $sha; size = $bytes.Length; content = [Convert]::ToBase64String($bytes) } | ConvertTo-Json -Depth 5)
}

function New-CanonicalBody {
    @'
Refs #100

- **Dispatch ID**: `req-100-trusted-gate-20260716-03`
'@
}

function Invoke-Sut {
    param([Parameter(Mandatory)][string] $FakeBin, [Parameter(Mandatory)][string] $PrJson, [string] $ContentJson = '{}', [string] $FailGh = '')
    $prFile = Join-Path $tempRoot ([guid]::NewGuid().ToString('N') + '-pr.json')
    $contentFile = Join-Path $tempRoot ([guid]::NewGuid().ToString('N') + '-content.json')
    $filesFile = Join-Path $tempRoot ([guid]::NewGuid().ToString('N') + '-files.jsonl')
    Set-Content -LiteralPath $prFile -Value $PrJson -Encoding UTF8
    Set-Content -LiteralPath $contentFile -Value $ContentJson -Encoding UTF8
    Set-Content -LiteralPath $filesFile -Value '{"filename":"scripts/governance/trusted-gate.ps1","status":"modified"}' -Encoding UTF8
    $oldPath = $env:PATH; $oldPr = $env:FAKE_PR; $oldContent = $env:FAKE_CONTENT; $oldFiles = $env:FAKE_FILES; $oldFail = $env:FAKE_GH_FAIL
    $artifact = Join-Path $tempRoot ([guid]::NewGuid().ToString('N') + '-artifacts')
    $env:PATH = "$FakeBin;$oldPath"; $env:FAKE_PR = $prFile; $env:FAKE_CONTENT = $contentFile; $env:FAKE_FILES = $filesFile; $env:FAKE_GH_FAIL = $FailGh
    Push-Location $repoRoot
    try {
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $scriptUnderTest -PRNumber 42 -Owner Sandape -Repo interCraft -ExpectedMasterSha ((git rev-parse HEAD).Trim()) -ArtifactDir $artifact 2>&1
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorAction
    }
    finally {
        Pop-Location
        $env:PATH = $oldPath; $env:FAKE_PR = $oldPr; $env:FAKE_CONTENT = $oldContent; $env:FAKE_FILES = $oldFiles; $env:FAKE_GH_FAIL = $oldFail
    }
    return [pscustomobject]@{ ExitCode = $exitCode; Text = (@($output | ForEach-Object { "$_" }) -join "`n"); Artifact = $artifact }
}

try {
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    $fakeBin = Join-Path $tempRoot 'bin'; New-FakeGh -Directory $fakeBin
    $workflow = Get-Content -Raw (Join-Path $repoRoot '.github/workflows/governance-gate.yml')
    $source = Get-Content -Raw $scriptUnderTest

    It 'workflow is pull_request_target-only with read permissions' {
        Assert-Contains $workflow 'pull_request_target:' 'workflow trigger missing'
        Assert-Contains $workflow 'contents: read' 'contents read permission missing'
        Assert-Contains $workflow 'pull-requests: read' 'pull requests read permission missing'
        Assert-Contains $workflow 'issues: read' 'issues read permission missing'
        Assert-True ($workflow -notmatch '(?m)^\s*pull_request:\s*$') 'untrusted pull_request trigger must not be present'
    }
    It 'workflow checks out exact master with credentials disabled and bounded timeout' {
        Assert-Contains $workflow 'git/ref/heads/master' 'master ref API resolution missing'
        Assert-Contains $workflow 'persist-credentials: false' 'persisted checkout credentials are unsafe'
        Assert-Contains $workflow 'timeout-minutes: 10' 'job timeout is not bounded'
        Assert-Contains $workflow 'if: always()' 'failure artifacts are not always uploaded'
    }
    It 'trusted runner never checks out or executes PR-head code' {
        Assert-Contains $source 'Copy-Item -LiteralPath' 'trusted gate copy missing'
        Assert-Contains $source 'Contents API response' 'authenticated Contents API read missing'
        Assert-Contains $source 'ref=\$HeadSha' 'immutable head SHA ref missing'
        Assert-True ($source -notmatch 'actions/checkout|Invoke-Expression|iex\s') 'trusted script contains an unsafe execution primitive'
    }
    It 'malformed Dispatch ID fails before Contents API use' {
        $r = Invoke-Sut -FakeBin $fakeBin -PrJson (New-PrJson -Body "Refs #100`n`n- **Dispatch ID**: BAD ID")
        Assert-True ($r.ExitCode -ne 0) 'malformed dispatch unexpectedly passed'
        Assert-Contains $r.Text 'GATE_DISPATCH_REF_MALFORMED' 'wrong error code for malformed dispatch'
        Assert-True (Test-Path (Join-Path $r.Artifact 'gate-result.json')) 'failure artifact missing'
    }
    It 'duplicate Dispatch ID fields fail closed' {
        $body = @'
Refs #100

- **Dispatch ID**: `req-100-trusted-gate-20260716-03`
- **Dispatch ID**: `req-100-trusted-gate-20260716-03`
'@
        $r = Invoke-Sut -FakeBin $fakeBin -PrJson (New-PrJson -Body $body)
        Assert-True ($r.ExitCode -ne 0) 'duplicate dispatch unexpectedly passed'
        Assert-Contains $r.Text 'GATE_DISPATCH_REF_MALFORMED' 'duplicate dispatch was not classified'
    }
    It 'wrong base target fails closed' {
        $r = Invoke-Sut -FakeBin $fakeBin -PrJson (New-PrJson -Body '**Dispatch ID**: req-100-trusted-gate-20260716-03' -BaseRef 'develop')
        Assert-True ($r.ExitCode -ne 0) 'wrong base unexpectedly passed'
        Assert-Contains $r.Text 'GATE_INVALID_TARGET' 'wrong-base failure was not structured'
    }
    It 'deleted fork or missing head repository fails closed' {
        $r = Invoke-Sut -FakeBin $fakeBin -PrJson (New-PrJson -Body '**Dispatch ID**: req-100-trusted-gate-20260716-03' -HeadRepo $null)
        Assert-True ($r.ExitCode -ne 0) 'missing head repository unexpectedly passed'
        Assert-Contains $r.Text 'GATE_PR_HEAD_RACE' 'missing fork failure was not classified as a race'
    }
    It 'Contents API path/type mismatch fails closed' {
        $r = Invoke-Sut -FakeBin $fakeBin -PrJson (New-PrJson -Body (New-CanonicalBody)) -ContentJson (New-ContentJson -Path '.github/dispatches/other.json' -Name 'other.json')
        Assert-True ($r.ExitCode -ne 0) 'path mismatch unexpectedly passed'
        Assert-Contains $r.Text 'GATE_DISPATCH_REF_MALFORMED' 'path mismatch was not structured'
    }
    It 'Contents API size limit fails closed' {
        $r = Invoke-Sut -FakeBin $fakeBin -PrJson (New-PrJson -Body (New-CanonicalBody)) -ContentJson (New-ContentJson -Size 65537)
        Assert-True ($r.ExitCode -ne 0) 'oversized dispatch unexpectedly passed'
        Assert-Contains $r.Text 'GATE_DISPATCH_REF_MALFORMED' 'oversize failure was not structured'
    }
    It 'canonical bullet and backtick Dispatch ID reaches the trusted gate boundary' {
        $r = Invoke-Sut -FakeBin $fakeBin -PrJson (New-PrJson -Body (New-CanonicalBody)) -ContentJson (New-ValidContentJson)
        Assert-True ($r.ExitCode -ne 0) 'fixture unexpectedly passed without complete GitHub authorities'
        Assert-Contains $r.Text 'Trusted gate result' 'canonical Dispatch ID was rejected before the gate boundary'
        Assert-Contains $r.Text 'GATE_DISPATCH_REF_MALFORMED' 'underlying trusted gate result was not preserved'
    }
    It 'GitHub API transport failure fails closed without secrets' {
        $r = Invoke-Sut -FakeBin $fakeBin -PrJson (New-PrJson) -FailGh '1'
        Assert-True ($r.ExitCode -ne 0) 'transport failure unexpectedly passed'
        Assert-Contains $r.Text 'GATE_TRANSPORT_FAILURE' 'transport failure was not structured'
        Assert-True ($r.Text -notmatch '(?i)password|token|authorization|postgresql://|redis://') 'failure output leaked a credential-like value'
    }
}
finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host ("TRUSTED GATE TESTS: {0} passed, {1} failed" -f $script:passed, $script:failed)
if ($script:failed -gt 0) { exit 1 }
exit 0
