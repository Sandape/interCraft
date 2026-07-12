<#
.SYNOPSIS
    Self-contained test harness for gate.ps1 PR Gate.

    Creates temp directories, a fake gh command on PATH (never touches real
    GitHub), and a fake dispatch.ps1 boundary. Runs comprehensive cases covering
    positive validation and all negative families. Exits 0 on all-pass, 1 on
    any failure.

    Usage:
        powershell -NoProfile -File gate.Tests.ps1
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptUnderTest = Join-Path $PSScriptRoot '..\gate.ps1'
$realDispatchScript = Join-Path $PSScriptRoot '..\dispatch.ps1'
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("intercraft-gate-test-{0}" -f [guid]::NewGuid().ToString('N'))
$script:passed = 0
$script:failed = 0

# ======================================================================
# Helpers
# ======================================================================

function It {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [scriptblock] $Test
    )
    try {
        & $Test
        $script:passed++
        Write-Host "PASS $Name"
    } catch {
        $script:failed++
        Write-Host "FAIL $Name :: $($_.Exception.Message) :: $($_.ScriptStackTrace)"
    }
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-ExitCode {
    param([int] $Actual, [int] $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message (expected exit $Expected, got $Actual)"
    }
}

function Assert-OutputContains {
    param([array] $Output, [string] $Pattern, [string] $Message)
    $text = @($Output | ForEach-Object { "$_" }) -join "`n"
    if ($text -notmatch $Pattern) {
        throw "$Message (expected pattern '$Pattern' not found in output)"
    }
}

# ======================================================================
# Fixture writers
# ======================================================================

function Write-MasterRefFixture {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [string] $Sha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    )
    $ref = @{ object = @{ sha = $Sha } }
    $ref | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Write-IssueFixture {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [string] $State = 'open',
        [switch] $PullRequest,
        [string] $Body = @"
# Test Issue

## Canonical Acceptance Statement

Implement the gate.

## Requested Allowed Paths

scripts/governance/**
docs/decisions/**
"@
    )
    $issue = @{ state = $State; body = $Body }
    if ($PullRequest) { $issue.pull_request = @{ url = 'https://api.github.test/pulls/19' } }
    $issue | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Write-PRFilesFixture {
    <#
    .SYNOPSIS
        Writes a JSON Lines fixture for paginated PR files endpoint.
        Each line is one JSON file object (as --jq '.[]' would output).
    #>
    param(
        [Parameter(Mandatory)] [string] $Path,
        [array] $Files
    )
    $lines = @()
    foreach ($f in $Files) {
        $lines += ($f | ConvertTo-Json -Compress -Depth 3)
    }
    [System.IO.File]::WriteAllLines($Path, $lines, [System.Text.Encoding]::UTF8)
}

function Write-AllPRsFixture {
    <#
    .SYNOPSIS
        Writes a JSON Lines fixture for paginated all-PRs endpoint.
    #>
    param(
        [Parameter(Mandatory)] [string] $Path,
        [array] $PRs
    )
    $lines = @()
    foreach ($pr in $PRs) {
        $lines += ($pr | ConvertTo-Json -Compress -Depth 3)
    }
    [System.IO.File]::WriteAllLines($Path, $lines, [System.Text.Encoding]::UTF8)
}

function Write-PRFixture {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [int] $Number = 42,
        [string] $State = 'open',
        [string] $BaseRef = 'master',
        [string] $BaseSha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        [string] $HeadSha = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        [string] $Body = '',
        [string] $Title = 'Test PR'
    )
    $pr = @{
        number = $Number
        state = $State
        title = $Title
        base = @{ ref = $BaseRef; sha = $BaseSha }
        head = @{ sha = $HeadSha }
        body = $Body
    }
    $pr | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Write-DispatchEnvelope {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $DispatchId,
        [int] $IssueNumber = 19,
        [string] $State = 'active',
        [string] $BaseSha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        [string] $AcHash = '1111111111111111111111111111111111111111111111111111111111111111',
        [array] $AllowedPaths = @('scripts/governance/**'),
        [string] $GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
    )
    $env = @{
        dispatch_id = $DispatchId
        issue_number = $IssueNumber
        driver = 'human'
        base_sha = $BaseSha
        spec_task_id = 'T208'
        ac_hash = $AcHash
        canonical_ac_text_version = 'v1'
        allowed_paths = $AllowedPaths
        governance_version = $GovernanceVersion
        created_at = '2026-07-12T00:00:00Z'
        state = $State
    }
    $env | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Path -Encoding UTF8
}

# ======================================================================
# Fake gh.cmd content
# ======================================================================
$fakeGhContent = @'
@echo off
setlocal disabledelayedexpansion

REM === Transport failure simulation ===
if defined INTERCRAFT_FAKE_FAIL (
    echo {"message":"simulated transport failure"}
    exit /b 1
)

REM === Detect --paginate flag (stripped for URL matching) ===
set PAGINATE=0
setlocal enabledelayedexpansion
set ALL_ARGS=%*
if not "!ALL_ARGS:--paginate=!" == "!ALL_ARGS!" set PAGINATE=1
endlocal & set PAGINATE=%PAGINATE%

REM === Master ref ===
echo %* | findstr /C:"git/ref/heads/master" >nul 2>nul
if not errorlevel 1 (
    if defined INTERCRAFT_FAKE_MASTER_REF (
        type "%INTERCRAFT_FAKE_MASTER_REF%"
    ) else (
        echo {"object":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}
    )
    exit /b 0
)

REM === Issues ===
echo %* | findstr /C:"issues/" >nul 2>nul
if not errorlevel 1 (
    if defined INTERCRAFT_FAKE_ISSUE (
        type "%INTERCRAFT_FAKE_ISSUE%"
    ) else (
        echo {"state":"open","body":"## Canonical Acceptance Statement\n\nAC\n\n## Requested Allowed Paths\n\nscripts/**"}
    )
    exit /b 0
)

REM === PR files (contains /files in URL) ===
echo %* | findstr /C:"/files" >nul 2>nul
if not errorlevel 1 (
    if defined INTERCRAFT_FAKE_REQUIRE_PAGINATE if not %PAGINATE%==1 (
        echo pagination required 1>&2
        exit /b 1
    )
    if defined INTERCRAFT_FAKE_PR_FILES (
        type "%INTERCRAFT_FAKE_PR_FILES%"
    ) else (
        echo {"filename":"scripts/governance/gate.ps1","status":"added"}
    )
    exit /b 0
)

REM === Compare ===
echo %* | findstr /C:"compare/" >nul 2>nul
if not errorlevel 1 (
    if defined INTERCRAFT_FAKE_COMPARE_STATUS (
        echo {"status":"%INTERCRAFT_FAKE_COMPARE_STATUS%","ahead_by":1,"behind_by":0}
    ) else (
        echo {"status":"ahead","ahead_by":1,"behind_by":0}
    )
    exit /b 0
)

REM === All PRs (contains pulls?state= or pulls?state=all) ===
echo %* | findstr /C:"?state=" >nul 2>nul
if not errorlevel 1 (
    if defined INTERCRAFT_FAKE_REQUIRE_PAGINATE if not %PAGINATE%==1 (
        echo pagination required 1>&2
        exit /b 1
    )
    if defined INTERCRAFT_FAKE_ALL_PRS (
        type "%INTERCRAFT_FAKE_ALL_PRS%"
    ) else (
        if %PAGINATE%==1 (
            echo {"number":42,"state":"open","body":"**Dispatch ID**: test-dispatch-01"}
        ) else (
            echo [{"number":42,"state":"open","body":"**Dispatch ID**: test-dispatch-01"}]
        )
    )
    exit /b 0
)

REM === Single pull request (pulls/NUMBER) ===
echo %* | findstr /C:"pulls/" >nul 2>nul
if not errorlevel 1 (
    if defined INTERCRAFT_FAKE_PR (
        type "%INTERCRAFT_FAKE_PR%"
    ) else (
        echo {"number":42,"state":"open","base":{"ref":"master","sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"head":{"sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"body":"Refs #19\n\n## Dispatch\n\n- **Dispatch ID**: test-dispatch-01\n\n## Evidence\n\nEvidence content","title":"Test PR"}
    )
    exit /b 0
)

REM === Unknown ===
echo {"message":"unknown api call"}
exit /b 1
'@

# ======================================================================
# Fake dispatch.ps1 content (validates dispatch file existence)
# ======================================================================
$fakeDispatchContent = @'
param(
    [string] $ValidateDispatchId,
    [int] $ValidateIssueNumber,
    [string] $StorePath,
    [string] $Owner,
    [string] $Repo
)

Set-StrictMode -Version Latest

$exitCode = $env:INTERCRAFT_FAKE_DISPATCH_EXIT
if ($exitCode -eq '0') { exit 0 }
if ($exitCode -eq '1') {
    Write-Error "ERROR: DISPATCH_INACTIVE: Simulated dispatch validation failure" -ErrorAction Continue
    exit 1
}

$dir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($StorePath)
$file = [System.IO.Path]::Combine($dir, "$ValidateDispatchId.json")
if (Test-Path -LiteralPath $file) { exit 0 } else { exit 1 }
'@

# ======================================================================
# Test environment factory
# ======================================================================
function New-TestEnv {
    param([string] $Prefix = 'gate')

    Clear-TestEnv
    $root = Join-Path $tempRoot ([guid]::NewGuid().ToString('N'))
    $store = Join-Path $root '.github\dispatches'
    $fakeBin = Join-Path $root 'bin'
    $governanceDir = Join-Path $root 'scripts\governance'
    $fixtures = Join-Path $root 'fixtures'

    New-Item -ItemType Directory -Path $store -Force | Out-Null
    New-Item -ItemType Directory -Path $fakeBin -Force | Out-Null
    New-Item -ItemType Directory -Path $governanceDir -Force | Out-Null
    New-Item -ItemType Directory -Path $fixtures -Force | Out-Null

    # Write fake gh.cmd
    Set-Content -LiteralPath (Join-Path $fakeBin 'gh.cmd') -Value $fakeGhContent -Encoding ASCII

    # Mirror the production repository layout. Both the validator and dispatch
    # store are derived from gate.ps1's location and have no caller override.
    Copy-Item -LiteralPath $scriptUnderTest -Destination (Join-Path $governanceDir 'gate.ps1')
    Set-Content -LiteralPath (Join-Path $governanceDir 'dispatch.ps1') -Value $fakeDispatchContent -Encoding ASCII

    # Prepend fake bin to PATH
    $env:PATH = "$fakeBin;$env:PATH"
    $env:INTERCRAFT_FAKE_REQUIRE_PAGINATE = '1'

    return [PSCustomObject]@{
        Root = $root
        Store = $store
        FakeBin = $fakeBin
        Fixtures = $fixtures
        DefaultDispatchId = 'test-dispatch-01'
        DefaultIssueNumber = 19
        DefaultPRNumber = 42
        DefaultBaseSha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        DefaultHeadSha = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
        GateScript = Join-Path $governanceDir 'gate.ps1'
        FakeDispatchScript = Join-Path $governanceDir 'dispatch.ps1'
    }
}

function Clear-TestEnv {
    $null = Remove-Item Env:\INTERCRAFT_FAKE_FAIL -ErrorAction SilentlyContinue
    $null = Remove-Item Env:\INTERCRAFT_FAKE_MASTER_REF -ErrorAction SilentlyContinue
    $null = Remove-Item Env:\INTERCRAFT_FAKE_ISSUE -ErrorAction SilentlyContinue
    $null = Remove-Item Env:\INTERCRAFT_FAKE_PR -ErrorAction SilentlyContinue
    $null = Remove-Item Env:\INTERCRAFT_FAKE_PR_FILES -ErrorAction SilentlyContinue
    $null = Remove-Item Env:\INTERCRAFT_FAKE_ALL_PRS -ErrorAction SilentlyContinue
    $null = Remove-Item Env:\INTERCRAFT_FAKE_COMPARE_STATUS -ErrorAction SilentlyContinue
    $null = Remove-Item Env:\INTERCRAFT_FAKE_DISPATCH_EXIT -ErrorAction SilentlyContinue
    $null = Remove-Item Env:\INTERCRAFT_FAKE_PAGINATE_COUNT -ErrorAction SilentlyContinue
    $null = Remove-Item Env:\INTERCRAFT_FAKE_REQUIRE_PAGINATE -ErrorAction SilentlyContinue
}

function Invoke-Gate {
    param(
        [Parameter(Mandatory)] [hashtable] $Parameters
    )
    $invokeParameters = @{}
    foreach ($entry in $Parameters.GetEnumerator()) {
        if ($entry.Key -notin @('DispatchScript', 'StorePath')) {
            $invokeParameters[$entry.Key] = $entry.Value
        }
    }
    # StorePath is a legacy test-harness locator only; it is never forwarded to
    # the production script, whose store path is fixed relative to itself.
    $githubDir = Split-Path $Parameters.StorePath -Parent
    $root = Split-Path $githubDir -Parent
    $testGate = Join-Path $root 'scripts\governance\gate.ps1'
    $output = & $testGate @invokeParameters 2>&1
    $exitCode = $LASTEXITCODE
    return [PSCustomObject]@{
        ExitCode = $exitCode
        Output = $output
    }
}

# ======================================================================
# Standard PR body generator
# ======================================================================
function Get-StandardPRBody {
    param(
        [string] $DispatchId = 'test-dispatch-01',
        [int] $IssueNum = 19
    )
    return @"
Refs #$IssueNum

## Dispatch

- **Dispatch ID**: $DispatchId

## Files Changed

- scripts/governance/gate.ps1 — PR Gate

## Checks Performed

- [ ] Preflight passed

## Evidence

Manual test evidence for this PR.

## Risk & Rollback

- **Risk**: Low
"@
}

function New-ReadyGateScenario {
    param(
        [string] $Body,
        [object[]] $AdditionalPRs = @(),
        [string] $CompareStatus = 'ahead'
    )

    $scenario = New-TestEnv
    $dispatchId = $scenario.DefaultDispatchId
    $baseSha = $scenario.DefaultBaseSha
    $headSha = $scenario.DefaultHeadSha
    if ([string]::IsNullOrEmpty($Body)) {
        $Body = Get-StandardPRBody -DispatchId $dispatchId
    }

    Write-DispatchEnvelope -Path (Join-Path $scenario.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $scenario.Fixtures 'master.json') -Sha $baseSha
    Write-PRFixture -Path (Join-Path $scenario.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $Body
    Write-IssueFixture -Path (Join-Path $scenario.Fixtures 'issue.json')
    Write-PRFilesFixture -Path (Join-Path $scenario.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1';status='added'})

    $prs = [System.Collections.Generic.List[object]]::new()
    $prs.Add(@{number=42;state='open';body=$Body;title='Current PR'})
    foreach ($otherPR in $AdditionalPRs) { $prs.Add($otherPR) }
    Write-AllPRsFixture -Path (Join-Path $scenario.Fixtures 'all_prs.jsonl') -PRs $prs.ToArray()

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $scenario.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $scenario.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $scenario.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $scenario.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $scenario.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = $CompareStatus
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    return $scenario
}

function Invoke-GhAndCapture {
    <#
    .SYNOPSIS
        Calls gh through fake PATH and returns exit code.
        Used to verify fake gh.cmd behavior.
    #>
    param([string[]] $Arguments)
    $output = & gh @Arguments 2>&1
    return @{ ExitCode = $LASTEXITCODE; Output = $output }
}

# ======================================================================
# Bootstrap
# ======================================================================
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

# ======================================================================
# Tests
# ======================================================================

try {

# ----------------------------------------------------------------------
# Test 1: Positive pass
# ----------------------------------------------------------------------
It 'passes all checks for a valid PR with matching dispatch' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $prNum = $env.DefaultPRNumber
    $issueNum = $env.DefaultIssueNumber
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    # Write dispatch envelope
    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -IssueNumber $issueNum -BaseSha $baseSha

    # Write master ref fixture
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    # Write PR fixture
    $prBody = Get-StandardPRBody -DispatchId $dispatchId -IssueNum $issueNum
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number $prNum -BaseSha $baseSha -HeadSha $headSha -Body $prBody

    # Write Issue fixture
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json') -State 'open'

    # Write PR files fixture (JSON Lines)
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1';status='added'})

    # Write all PRs fixture (JSON Lines) — only the current PR
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=$prNum;state='open';body="**Dispatch ID**: $dispatchId";title='Test PR'})

    # Set env vars for fake gh
    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = $prNum
        DispatchId = $dispatchId
        StorePath = $env.Store
        Owner = 'Sandape'
        Repo = 'interCraft'
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Positive gate should pass"
    Assert-OutputContains -Output $result.Output -Pattern '"passed":\s*true' -Message "Output should indicate pass"
}

# ----------------------------------------------------------------------
# Test 2: Missing Refs #N
# ----------------------------------------------------------------------
It 'fails when PR body has no Refs #N' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $badBody = "# PR without Refs`n`nJust some text.`n`n## Dispatch`n`n- **Dispatch ID**: $dispatchId"
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $badBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Missing Refs should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_ISSUE_REF' -Message "Error code should be GATE_MISSING_ISSUE_REF"
}

# ----------------------------------------------------------------------
# Test 3: Duplicate Refs #N
# ----------------------------------------------------------------------
It 'fails when PR body has duplicate Refs #N' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $badBody = "Refs #19`n`nRefs #20`n`n## Dispatch`n`n- **Dispatch ID**: $dispatchId"
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $badBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Duplicate Refs should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_ISSUE_REF' -Message "Error code should be GATE_MISSING_ISSUE_REF"
}

# ----------------------------------------------------------------------
# Test 4: Missing Dispatch ID in PR body
# ----------------------------------------------------------------------
It 'fails when PR body has no Dispatch ID field' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $badBody = "Refs #19`n`n## Dispatch`n`nNo Dispatch ID field here."
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $badBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Missing Dispatch ID should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DISPATCH_REF_MALFORMED' -Message "Error code should be GATE_DISPATCH_REF_MALFORMED"
}

# ----------------------------------------------------------------------
# Test 5: Mismatched Dispatch ID
# ----------------------------------------------------------------------
It 'fails when PR body Dispatch ID does not match requested dispatch' {
    $env = New-TestEnv
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store 'test-dispatch-01.json') `
        -DispatchId 'test-dispatch-01' -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    # PR body says dispatch-99, but we request dispatch-01
    $badBody = "Refs #19`n`n## Dispatch`n`n- **Dispatch ID**: wrong-dispatch-99"
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $badBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = 'test-dispatch-01'; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Mismatched Dispatch ID should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DISPATCH_REF_MALFORMED' -Message "Error code should be GATE_DISPATCH_REF_MALFORMED"
}

# ----------------------------------------------------------------------
# Test 6: Dispatch validate failure
# ----------------------------------------------------------------------
It 'fails when dispatch validation fails' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '1'  # dispatch fails

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Dispatch validation failure should fail gate"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DISPATCH_INACTIVE' -Message "Error code should be GATE_DISPATCH_INACTIVE"
}

# ----------------------------------------------------------------------
# Test 7: Dispatch file not found
# ----------------------------------------------------------------------
It 'fails when dispatch file does not exist' {
    $env = New-TestEnv
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha
    $prBody = Get-StandardPRBody -DispatchId 'nonexistent-dispatch'
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    # Don't create dispatch file

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = 'nonexistent-dispatch'; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Missing dispatch file should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DISPATCH_NOT_FOUND' -Message "Error code should be GATE_DISPATCH_NOT_FOUND"
}

# ----------------------------------------------------------------------
# Test 8: Dispatch inactive (expired)
# ----------------------------------------------------------------------
It 'fails when dispatch envelope state is not active' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    # Create dispatch with expired state
    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha -State 'expired'
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '1'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Inactive dispatch should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DISPATCH_INACTIVE' -Message "Error code should be GATE_DISPATCH_INACTIVE"
}

# ----------------------------------------------------------------------
# Test 9: Envelope issue number mismatch
# ----------------------------------------------------------------------
It 'fails when envelope issue_number does not match Refs N' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    # Envelope says Issue 99 but PR says Refs #19
    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha -IssueNumber 99
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId -IssueNum 19
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Issue number mismatch should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_ISSUE_REF' -Message "Error code should be GATE_MISSING_ISSUE_REF"
}

# ----------------------------------------------------------------------
# Test 10: Issue not open
# ----------------------------------------------------------------------
It 'fails when referenced Issue is closed' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json') -State 'closed'

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Closed Issue should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_ISSUE_NOT_OPEN' -Message "Error code should be GATE_ISSUE_NOT_OPEN"
}

# ----------------------------------------------------------------------
# Test 11: PR not targeting master
# ----------------------------------------------------------------------
It 'fails when PR base ref is not master' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseRef 'develop' -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Non-master target should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_INVALID_TARGET' -Message "Error code should be GATE_INVALID_TARGET"
}

# ----------------------------------------------------------------------
# Test 12: Stale master (base SHA != authoritative master)
# ----------------------------------------------------------------------
It 'fails when envelope base SHA does not equal authoritative master' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    # Dispatch envelope base_sha = aaaa...
    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    # Authoritative master is different: bbbb...
    $newMasterSha = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $newMasterSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Stale master should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_BASE_NOT_AUTHORITATIVE' -Message "Error code should be GATE_BASE_NOT_AUTHORITATIVE"
}

# ----------------------------------------------------------------------
# Test 13: PR base SHA mismatch
# ----------------------------------------------------------------------
It 'fails when PR base SHA does not match envelope base SHA' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    # PR base sha is different from envelope base
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha 'cccccccccccccccccccccccccccccccccccccccc' -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "PR base SHA mismatch should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_BASE_STALE' -Message "Error code should be GATE_BASE_STALE"
}

# ----------------------------------------------------------------------
# Test 14: Non-ancestor (compare behind/diverged)
# ----------------------------------------------------------------------
It 'fails when PR head does not descend from base (compare diverged)' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    # Compare API says diverged
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1';status='added'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'diverged'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Diverged ancestry should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_BASE_STALE' -Message "Error code should be GATE_BASE_STALE"
}

# ----------------------------------------------------------------------
# Test 15: Empty changed files
# ----------------------------------------------------------------------
It 'fails when PR has no changed files' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    # Empty PR files (no lines)
    Set-Content -LiteralPath (Join-Path $env.Fixtures 'pr_files.jsonl') -Value '' -Encoding UTF8
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Empty files should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_PATH_ESCAPE' -Message "Error code should be GATE_PATH_ESCAPE"
}

# ----------------------------------------------------------------------
# Test 16: Path escape
# ----------------------------------------------------------------------
It 'fails when PR file is outside allowed paths' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    # Allowed paths: scripts/governance/**
    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha -AllowedPaths @('scripts/governance/**')
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    # PR modifies src/product/ which is outside scripts/governance/**
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='src/product/code.ts';status='modified'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Path escape should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_PATH_ESCAPE' -Message "Error code should be GATE_PATH_ESCAPE"
}

# ----------------------------------------------------------------------
# Test 17: Case-only path mismatch
# ----------------------------------------------------------------------
It 'fails when PR file path matches only by case' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    # Allowed: Scripts/Governance/** (Capital S and G)
    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha -AllowedPaths @('Scripts/Governance/**')
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    # PR file uses lowercase scripts/governance/ (different case)
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1';status='added'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Case-only path mismatch should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_PATH_ESCAPE' -Message "Error code should be GATE_PATH_ESCAPE"
}

# ----------------------------------------------------------------------
# Test 18: Duplicate open PR for same dispatch
# ----------------------------------------------------------------------
It 'fails when another open PR references the same Dispatch ID' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1';status='added'})

    # All PRs include current PR (42) AND another open PR (99) with same dispatch
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(
            @{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Current PR'},
            @{number=99;state='open';body="**Dispatch ID**: $dispatchId";title='Duplicate PR'}
        )

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Duplicate open PR should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DUPLICATE_PR' -Message "Error code should be GATE_DUPLICATE_PR"
}

# ----------------------------------------------------------------------
# Test 19: Consumed (merged) PR for same dispatch
# ----------------------------------------------------------------------
It 'fails when dispatch was already consumed by a merged PR' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1';status='added'})

    # All PRs include current PR (42) AND a merged PR (99) with same dispatch
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(
            @{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Current PR'},
            @{number=99;state='merged';body="**Dispatch ID**: $dispatchId";title='Consumed PR'}
        )

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Consumed dispatch should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DUPLICATE_PR' -Message "Error code should be GATE_DUPLICATE_PR"
}

# ----------------------------------------------------------------------
# Test 20: Missing Evidence heading
# ----------------------------------------------------------------------
It 'fails when PR body lacks Evidence section' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    # PR body without Evidence section
    $badBody = "Refs #19`n`n## Dispatch`n`n- **Dispatch ID**: $dispatchId`n`n## Files Changed`n`n- file.ts"
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $badBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1';status='added'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Missing Evidence should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_EVIDENCE' -Message "Error code should be GATE_MISSING_EVIDENCE"
}

# ----------------------------------------------------------------------
# Test 21: Empty/whitespace-only Evidence
# ----------------------------------------------------------------------
It 'fails when Evidence section has only whitespace' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    # Evidence with only whitespace
    $badBody = "Refs #19`n`n## Dispatch`n`n- **Dispatch ID**: $dispatchId`n`n## Evidence`n`n   `n`t`n## Other"
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $badBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1';status='added'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Empty Evidence content should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_EVIDENCE' -Message "Error code should be GATE_MISSING_EVIDENCE"
}

# ----------------------------------------------------------------------
# Test 22: Comment-only Evidence
# ----------------------------------------------------------------------
It 'fails when Evidence has only HTML comments' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    # Evidence with only HTML comments
    $badBody = "Refs #19`n`n## Dispatch`n`n- **Dispatch ID**: $dispatchId`n`n## Evidence`n`n<!-- nothing here -->"
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $badBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1';status='added'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Comment-only Evidence should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_EVIDENCE' -Message "Error code should be GATE_MISSING_EVIDENCE"
}

# ----------------------------------------------------------------------
# Test 23: Invalid JSON from gh api
# ----------------------------------------------------------------------
It 'fails closed when gh returns invalid JSON' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha

    # Write a PR fixture with malformed JSON (no problem - gh.cmd outputs this)
    Set-Content -LiteralPath (Join-Path $env.Fixtures 'issue.json') -Value '{not-valid-json' -Encoding ASCII

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -Body $prBody

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Invalid JSON should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_JSON_PARSE_FAILED' -Message "Error code should be GATE_JSON_PARSE_FAILED"
}

# ----------------------------------------------------------------------
# Test 24: Transport failure (gh api non-zero)
# ----------------------------------------------------------------------
It 'fails closed when gh api returns non-zero exit' {
    $env = New-TestEnv
    $env:INTERCRAFT_FAKE_FAIL = '1'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = 'test-dispatch-01'; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Transport failure should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_TRANSPORT_FAILURE' -Message "Error code should be GATE_TRANSPORT_FAILURE"
}

# ----------------------------------------------------------------------
# Test 25: Path with traversal
# ----------------------------------------------------------------------
It 'fails when PR file contains path traversal' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    # File with traversal
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/../../../etc/passwd';status='added'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Path traversal should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_PATH_ESCAPE' -Message "Error code should be GATE_PATH_ESCAPE"
}

# ----------------------------------------------------------------------
# Test 26: Path with .git
# ----------------------------------------------------------------------
It 'fails when PR file contains .git segment' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='.git/config';status='modified'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message ".git path should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_PATH_ESCAPE' -Message "Error code should be GATE_PATH_ESCAPE"
}

# ----------------------------------------------------------------------
# Test 27: Path with control characters
# ----------------------------------------------------------------------
It 'fails when PR file contains control characters' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    # File with control char
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename="scripts/governance/`tgate.ps1";status='added'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Control chars in path should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_PATH_ESCAPE' -Message "Error code should be GATE_PATH_ESCAPE"
}

# ----------------------------------------------------------------------
# Test 28: PR is not open (closed)
# ----------------------------------------------------------------------
It 'fails when PR state is not open' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -State 'closed' -BaseSha $baseSha -HeadSha $headSha -Body $prBody

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Closed PR should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_INVALID_TARGET' -Message "Error code should be GATE_INVALID_TARGET"
}

# ----------------------------------------------------------------------
# Test 29: One full page is valid with gh --paginate
# ----------------------------------------------------------------------
It 'accepts exactly 100 items when gh --paginate completes' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    # Generate exactly 100 PR file entries
    $files = @()
    1..100 | ForEach-Object {
        $files += @{filename="scripts/governance/file$_.ps1";status='added'}
    }
    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') -Files $files

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "A complete 100-item page should pass"
    Assert-OutputContains -Output $result.Output -Pattern '"passed":true' -Message "Gate should pass with a complete full page"
}

# ----------------------------------------------------------------------
# Test 30: Path with colon (ADS)
# ----------------------------------------------------------------------
It 'fails when PR file contains a colon (ADS)' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='scripts/governance/gate.ps1:zone.identifier';status='added'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Colon in path should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_PATH_ESCAPE' -Message "Error code should be GATE_PATH_ESCAPE"
}

# ----------------------------------------------------------------------
# Test 31: Absolute path
# ----------------------------------------------------------------------
It 'fails when PR file is an absolute path' {
    $env = New-TestEnv
    $dispatchId = $env.DefaultDispatchId
    $baseSha = $env.DefaultBaseSha
    $headSha = $env.DefaultHeadSha

    Write-DispatchEnvelope -Path (Join-Path $env.Store "$dispatchId.json") `
        -DispatchId $dispatchId -BaseSha $baseSha
    Write-MasterRefFixture -Path (Join-Path $env.Fixtures 'master.json') -Sha $baseSha

    $prBody = Get-StandardPRBody -DispatchId $dispatchId
    Write-PRFixture -Path (Join-Path $env.Fixtures 'pr.json') `
        -Number 42 -BaseSha $baseSha -HeadSha $headSha -Body $prBody
    Write-IssueFixture -Path (Join-Path $env.Fixtures 'issue.json')

    Write-PRFilesFixture -Path (Join-Path $env.Fixtures 'pr_files.jsonl') `
        -Files @(@{filename='/etc/passwd';status='added'})
    Write-AllPRsFixture -Path (Join-Path $env.Fixtures 'all_prs.jsonl') `
        -PRs @(@{number=42;state='open';body="**Dispatch ID**: $dispatchId";title='Test'})

    $env:INTERCRAFT_FAKE_MASTER_REF = Join-Path $env.Fixtures 'master.json'
    $env:INTERCRAFT_FAKE_PR = Join-Path $env.Fixtures 'pr.json'
    $env:INTERCRAFT_FAKE_ISSUE = Join-Path $env.Fixtures 'issue.json'
    $env:INTERCRAFT_FAKE_PR_FILES = Join-Path $env.Fixtures 'pr_files.jsonl'
    $env:INTERCRAFT_FAKE_ALL_PRS = Join-Path $env.Fixtures 'all_prs.jsonl'
    $env:INTERCRAFT_FAKE_COMPARE_STATUS = 'ahead'
    $env:INTERCRAFT_FAKE_DISPATCH_EXIT = '0'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $env.Store
        DispatchScript = $env.FakeDispatchScript
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Absolute path should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_PATH_ESCAPE' -Message "Error code should be GATE_PATH_ESCAPE"
}

# ----------------------------------------------------------------------
# Test 32: Backticked Dispatch ID in another consumed PR
# ----------------------------------------------------------------------
It 'detects a backticked Dispatch ID in another consumed PR' {
    $dispatchId = 'test-dispatch-01'
    $otherBody = "## Dispatch`n`n- **Dispatch ID**: ``$dispatchId``"
    $scenario = New-ReadyGateScenario -AdditionalPRs @(
        @{number=99;state='closed';body=$otherBody;title='Consumed PR'}
    )

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $dispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Backticked consumed dispatch should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DUPLICATE_PR' -Message "Error code should be GATE_DUPLICATE_PR"
}

# ----------------------------------------------------------------------
# Test 33: Duplicate Evidence heading
# ----------------------------------------------------------------------
It 'fails when PR body contains duplicate Evidence headings' {
    $body = (Get-StandardPRBody) + "`n`n## Evidence`n`nSecond evidence block."
    $scenario = New-ReadyGateScenario -Body $body

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Duplicate Evidence heading should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_EVIDENCE' -Message "Error code should be GATE_MISSING_EVIDENCE"
}

# ----------------------------------------------------------------------
# Test 34: Placeholder-only Evidence
# ----------------------------------------------------------------------
It 'fails when Evidence contains only a placeholder' {
    $body = (Get-StandardPRBody) -replace 'Manual test evidence for this PR\.', 'TBD'
    $scenario = New-ReadyGateScenario -Body $body

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Placeholder-only Evidence should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_EVIDENCE' -Message "Error code should be GATE_MISSING_EVIDENCE"
}

# ----------------------------------------------------------------------
# Test 35: Unknown compare status
# ----------------------------------------------------------------------
It 'fails closed on an unknown compare status' {
    $scenario = New-ReadyGateScenario -CompareStatus 'mystery'

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Unknown compare status should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_BASE_STALE' -Message "Error code should be GATE_BASE_STALE"
}

# ----------------------------------------------------------------------
# Test 36: Unsafe caller-supplied Dispatch ID
# ----------------------------------------------------------------------
It 'rejects a traversal Dispatch ID before any API or file access' {
    $scenario = New-TestEnv

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = '../outside'; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Traversal Dispatch ID should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DISPATCH_REF_MALFORMED' -Message "Error code should be GATE_DISPATCH_REF_MALFORMED"
}

# ----------------------------------------------------------------------
# Test 37: Missing required PR API property
# ----------------------------------------------------------------------
It 'fails with structured JSON when PR metadata is missing a required property' {
    $scenario = New-ReadyGateScenario
    $prFixture = Get-Content -LiteralPath $env:INTERCRAFT_FAKE_PR -Raw | ConvertFrom-Json
    $prFixture.PSObject.Properties.Remove('head')
    Set-Content -LiteralPath $env:INTERCRAFT_FAKE_PR `
        -Value ($prFixture | ConvertTo-Json -Depth 10 -Compress) -Encoding UTF8

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Missing PR head should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_JSON_PARSE_FAILED' -Message "Error code should be GATE_JSON_PARSE_FAILED"
}

# ----------------------------------------------------------------------
# Test 38: Non-positive Issue reference
# ----------------------------------------------------------------------
It 'rejects Refs zero before requesting an Issue' {
    $body = (Get-StandardPRBody) -replace 'Refs #19', 'Refs #0'
    $scenario = New-ReadyGateScenario -Body $body

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Refs zero should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_ISSUE_REF' -Message "Error code should be GATE_MISSING_ISSUE_REF"
}

# ----------------------------------------------------------------------
# Test 39: CommonMark-invalid closing fence must not expose hidden fields
# ----------------------------------------------------------------------
It 'keeps governance fields inside a fence when marker has trailing text' {
    $body = @'
```text
```not-a-close
Refs #19

## Dispatch

- **Dispatch ID**: test-dispatch-01

## Evidence

Fake evidence.
'@
    $scenario = New-ReadyGateScenario -Body $body

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Fields inside an unclosed CommonMark fence should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_ISSUE_REF' -Message "Error code should be GATE_MISSING_ISSUE_REF"
}

# ----------------------------------------------------------------------
# Test 40: Duplicate Dispatch heading after an intervening section
# ----------------------------------------------------------------------
It 'fails when a later peer section is followed by a second Dispatch heading' {
    $body = (Get-StandardPRBody) + "`n`n## Notes`n`nIntervening section.`n`n## Dispatch`n`n- **Dispatch ID**: test-dispatch-01"
    $scenario = New-ReadyGateScenario -Body $body

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Duplicate Dispatch heading should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DISPATCH_REF_MALFORMED' -Message "Error code should be GATE_DISPATCH_REF_MALFORMED"
}

# ----------------------------------------------------------------------
# Test 41: Rename source path must also be allowlisted
# ----------------------------------------------------------------------
It 'fails when a rename moves an out-of-scope source into an allowed path' {
    $scenario = New-ReadyGateScenario
    Write-PRFilesFixture -Path $env:INTERCRAFT_FAKE_PR_FILES -Files @(
        @{filename='scripts/governance/security.ts';previous_filename='src/security.ts';status='renamed'}
    )

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Out-of-scope rename source should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_PATH_ESCAPE' -Message "Error code should be GATE_PATH_ESCAPE"
}

# ----------------------------------------------------------------------
# Test 42: Renamed entry must supply previous_filename
# ----------------------------------------------------------------------
It 'fails closed when a renamed file entry omits previous_filename' {
    $scenario = New-ReadyGateScenario
    Write-PRFilesFixture -Path $env:INTERCRAFT_FAKE_PR_FILES -Files @(
        @{filename='scripts/governance/security.ts';status='renamed'}
    )

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Missing previous_filename should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_JSON_PARSE_FAILED' -Message "Error code should be GATE_JSON_PARSE_FAILED"
}

# ----------------------------------------------------------------------
# Test 43: Refs must resolve to an Issue, not a PR
# ----------------------------------------------------------------------
It 'rejects Refs that resolves to an open Pull Request' {
    $scenario = New-ReadyGateScenario
    Write-IssueFixture -Path $env:INTERCRAFT_FAKE_ISSUE -State 'open' -PullRequest

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Pull Request must not satisfy governance Issue reference"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_ISSUE_REF' -Message "Error code should be GATE_MISSING_ISSUE_REF"
}

# ----------------------------------------------------------------------
# Test 44: Indented Refs is Markdown code
# ----------------------------------------------------------------------
It 'ignores a four-space-indented Refs line' {
    $body = (Get-StandardPRBody) -replace '^Refs #19', '    Refs #19'
    $scenario = New-ReadyGateScenario -Body $body

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Indented Refs should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_ISSUE_REF' -Message "Error code should be GATE_MISSING_ISSUE_REF"
}

# ----------------------------------------------------------------------
# Test 45: Indented Dispatch field is Markdown code
# ----------------------------------------------------------------------
It 'ignores a four-space-indented Dispatch ID field' {
    $body = (Get-StandardPRBody) -replace '- \*\*Dispatch ID\*\*:', '    - **Dispatch ID**:'
    $scenario = New-ReadyGateScenario -Body $body

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Indented Dispatch field should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_DISPATCH_REF_MALFORMED' -Message "Error code should be GATE_DISPATCH_REF_MALFORMED"
}

# ----------------------------------------------------------------------
# Test 46: Evidence heading must be exactly level two
# ----------------------------------------------------------------------
It 'rejects a non-level-two Evidence heading' {
    $body = (Get-StandardPRBody) -replace '## Evidence', '### Evidence'
    $scenario = New-ReadyGateScenario -Body $body

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Evidence heading at wrong level should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_MISSING_EVIDENCE' -Message "Error code should be GATE_MISSING_EVIDENCE"
}

# ----------------------------------------------------------------------
# Test 47: gh executable cannot be started
# ----------------------------------------------------------------------
It 'returns structured transport failure when gh is unavailable' {
    $scenario = New-ReadyGateScenario
    $emptyPath = Join-Path $scenario.Root 'no-gh'
    New-Item -ItemType Directory -Path $emptyPath -Force | Out-Null
    $env:PATH = $emptyPath

    $result = Invoke-Gate -Parameters @{
        PRNumber = 42; DispatchId = $scenario.DefaultDispatchId; StorePath = $scenario.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Missing gh should fail"
    Assert-OutputContains -Output $result.Output -Pattern 'GATE_TRANSPORT_FAILURE' -Message "Error code should be GATE_TRANSPORT_FAILURE"
}

} finally {
    # Cleanup temp root
    $resolvedTemp = [IO.Path]::GetFullPath($tempRoot)
    $resolvedSystemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolvedTemp.StartsWith($resolvedSystemTemp, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolvedTemp -Leaf).StartsWith('intercraft-gate-test-', [StringComparison]::Ordinal)) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "RESULT passed=$script:passed failed=$script:failed"
if ($script:failed -gt 0) { exit 1 }
