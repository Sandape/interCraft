<#
.SYNOPSIS
    Self-contained test harness for dispatch.ps1 state machine.

    Creates temp directories, a fake gh command on PATH (never touches real
    GitHub), and runs at least 12 test cases covering all operations and
    edge cases. Exits 0 on all-pass, 1 on any failure.

    Usage:
        powershell -NoProfile -File dispatch.Tests.ps1
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptUnderTest = Join-Path $PSScriptRoot '..\dispatch.ps1'
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("intercraft-dispatch-test-{0}" -f [guid]::NewGuid().ToString('N'))
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
        Write-Host "FAIL $Name :: $($_.Exception.Message)"
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

function Write-IssueJson {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [string] $Body = "# Test`n`n## Canonical Acceptance Statement`n`nAC content`n`n## Requested Allowed Paths`n`nsrc/**`ndocs/**",
        [string] $State = 'open'
    )
    $issue = @{ state = $State; body = $Body }
    $issue | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function New-TestEnv {
    <#
    .SYNOPSIS
        Creates a temporary test environment with a fake gh.cmd on PATH.
    #>
    param([string] $Prefix = 'test')

    Clear-TestEnv
    $root = Join-Path $tempRoot ([guid]::NewGuid().ToString('N'))
    $store = Join-Path $root 'dispatches'
    $fakeBin = Join-Path $root 'bin'
    $issuesDir = Join-Path $root 'issues'

    New-Item -ItemType Directory -Path $store -Force | Out-Null
    New-Item -ItemType Directory -Path $fakeBin -Force | Out-Null
    New-Item -ItemType Directory -Path $issuesDir -Force | Out-Null

    # Write fake gh.cmd
    $fakeGhContent = @'
@echo off
setlocal disabledelayedexpansion

REM === Transport failure simulation ===
if defined INTERCRAFT_FAKE_FAIL (
    echo {"message":"simulated transport failure"}
    exit /b 1
)

REM === Master ref ===
echo %* | findstr /C:"git/ref/heads/master" >nul 2>nul
if not errorlevel 1 (
    if defined INTERCRAFT_FAKE_MASTER_SHA (
        echo {"object":{"sha":"%INTERCRAFT_FAKE_MASTER_SHA%"}}
    ) else (
        echo {"object":{"sha":"0000000000000000000000000000000000000000"}}
    )
    exit /b 0
)

REM === Issues ===
echo %* | findstr /C:"issues/" >nul 2>nul
if not errorlevel 1 (
    if defined INTERCRAFT_FAKE_ISSUE_PATH (
        if exist "%INTERCRAFT_FAKE_ISSUE_PATH%" (
            type "%INTERCRAFT_FAKE_ISSUE_PATH%"
        ) else (
            echo {"state":"open","body":"# Test\n\n## Canonical Acceptance Statement\n\nAC content\n\n## Requested Allowed Paths\n\nscripts/**"}
        )
    ) else (
        echo {"state":"open","body":"# Test\n\n## Canonical Acceptance Statement\n\nAC content\n\n## Requested Allowed Paths\n\nscripts/**"}
    )
    exit /b 0
)

REM === Unknown ===
echo {"message":"unknown api call"}
exit /b 1
'@

    Set-Content -LiteralPath (Join-Path $fakeBin 'gh.cmd') -Value $fakeGhContent -Encoding ASCII

    # Prepend fake bin to PATH
    $env:PATH = "$fakeBin;$env:PATH"

    return [PSCustomObject]@{
        Root = $root
        Store = $store
        FakeBin = $fakeBin
        IssuesDir = $issuesDir
    }
}

function Clear-TestEnv {
    <#
    .SYNOPSIS
        Cleans up test environment variables to prevent cross-test leakage.
    #>
    $null = Remove-Item Env:\INTERCRAFT_FAKE_FAIL -ErrorAction SilentlyContinue
}

function Invoke-Dispatch {
    <#
    .SYNOPSIS
        Runs dispatch.ps1 with hashtable splatting and returns exit code.
    #>
    param(
        [Parameter(Mandatory)] [hashtable] $Parameters
    )

    $output = & $scriptUnderTest @Parameters 2>&1
    $exitCode = $LASTEXITCODE

    return [PSCustomObject]@{
        ExitCode = $exitCode
        Output = $output
    }
}

# ======================================================================
# Test data helpers
# ======================================================================

function Get-StandardAcBody {
    return @"
# Test Issue

## Canonical Acceptance Statement

Implement the dispatch state machine with Create, Validate, Supersede, and Expire operations.

## Requested Allowed Paths

scripts/governance/**
docs/decisions/**

## Additional Notes

Some notes here.
"@
}

# ======================================================================
# Create root temp dir
# ======================================================================
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

# ======================================================================
# Tests
# ======================================================================

try {

# --- Test 1: Positive Create ---
It 'creates a valid dispatch' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFile = Join-Path $env.IssuesDir 'issue_1.json'
    Write-IssueJson -Path $issueFile -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-01'
        IssueNumber = 1
        Driver = 'human'
        SpecTaskId = 'T206'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**', 'docs/decisions/**')
        StorePath = $env.Store
    }

    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create should succeed"
    $dispatchFile = Join-Path $env.Store 'req-064-test-20260712-01.json'
    Assert-True (Test-Path -LiteralPath $dispatchFile) "Dispatch file not created"

    $content = Get-Content -LiteralPath $dispatchFile -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($content.state -eq 'active') "State should be active"
    Assert-True ($content.issue_number -eq 1) "Issue number should be 1"
    Assert-True ($content.dispatch_id -eq 'req-064-test-20260712-01') "dispatch_id mismatch"
    Assert-True ($content.driver -eq 'human') "Driver mismatch"
    Assert-True ($content.base_sha -eq 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa') "base_sha mismatch"
}

# --- Test 2: Positive Validate ---
It 'validates a newly created dispatch' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFile = Join-Path $env.IssuesDir 'issue_2.json'
    Write-IssueJson -Path $issueFile -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-02'
        IssueNumber = 2
        Driver = 'codex'
        SpecTaskId = 'T207'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create should succeed"

    $result2 = Invoke-Dispatch -Parameters @{
        ValidateDispatchId = 'req-064-test-20260712-02'
        ValidateIssueNumber = 2
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 0 -Message "Validate should succeed"
}

# --- Test 3: Cross-driver singleton collision ---
It 'rejects cross-driver Create collision and leaves the first dispatch active' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFile = Join-Path $env.IssuesDir 'issue_3.json'
    Write-IssueJson -Path $issueFile -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = 'cccccccccccccccccccccccccccccccccccccccc'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    # Create first dispatch (human driver)
    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-31'
        IssueNumber = 3
        Driver = 'human'
        SpecTaskId = 'T206'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "First create should succeed"

    # A different driver cannot steal the Issue with an ordinary Create.
    $result2 = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-32'
        IssueNumber = 3
        Driver = 'codex'
        SpecTaskId = 'T206'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 1 -Message "Cross-driver Create should be rejected"

    # Verify the original dispatch remains active and no new file appeared.
    $oldFile = Join-Path $env.Store 'req-064-test-20260712-31.json'
    $oldContent = Get-Content -LiteralPath $oldFile -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($oldContent.state -eq 'active') "Original dispatch must remain active, got '$($oldContent.state)'"
    $newFile = Join-Path $env.Store 'req-064-test-20260712-32.json'
    Assert-True (-not (Test-Path -LiteralPath $newFile)) "Rejected collision must not create a second dispatch"

    # The original remains valid.
    $result3 = Invoke-Dispatch -Parameters @{
        ValidateDispatchId = 'req-064-test-20260712-31'
        ValidateIssueNumber = 3
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result3.ExitCode -Expected 0 -Message "Original dispatch should remain valid"
}

# --- Test 4: Stale base rejection ---
It 'rejects validate when base SHA no longer matches authoritative master' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFile = Join-Path $env.IssuesDir 'issue_4.json'
    Write-IssueJson -Path $issueFile -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = 'dddddddddddddddddddddddddddddddddddddddd'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-04'
        IssueNumber = 4
        Driver = 'human'
        SpecTaskId = 'T207'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create should succeed"

    # Validate with DIFFERENT master SHA (stale base)
    $env:INTERCRAFT_FAKE_MASTER_SHA = 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'

    $result2 = Invoke-Dispatch -Parameters @{
        ValidateDispatchId = 'req-064-test-20260712-04'
        ValidateIssueNumber = 4
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 1 -Message "Validate should fail on stale base"
}

# --- Test 5: Transport failure ---
It 'fails closed when gh api returns non-zero exit' {
    $env = New-TestEnv
    $env:INTERCRAFT_FAKE_FAIL = '1'

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-05'
        IssueNumber = 5
        Driver = 'human'
        SpecTaskId = 'T207'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Create should fail on gh transport failure"
}

# --- Test 6: Missing AC heading ---
It 'rejects create when Issue body has no Canonical Acceptance Statement heading' {
    $env = New-TestEnv
    $badBody = "# No AC Here`n`nJust some text without the required heading.`n`n## Requested Allowed Paths`n`nsrc/**"
    $issueFile = Join-Path $env.IssuesDir 'issue_6.json'
    Write-IssueJson -Path $issueFile -Body $badBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = 'ffffffffffffffffffffffffffffffffffffffff'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-06'
        IssueNumber = 6
        Driver = 'human'
        SpecTaskId = 'T207'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Create should fail on missing AC heading"
}

# --- Test 7: Duplicate AC heading ---
It 'rejects create when Issue body has duplicate Canonical Acceptance Statement headings' {
    $env = New-TestEnv
    $badBody = @"
# Test

## Canonical Acceptance Statement

First AC content.

## Some Other Section

More content.

## Canonical Acceptance Statement

Second AC content.
"@
    $issueFile = Join-Path $env.IssuesDir 'issue_7.json'
    Write-IssueJson -Path $issueFile -Body $badBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = '1111111111111111111111111111111111111111'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-07'
        IssueNumber = 7
        Driver = 'human'
        SpecTaskId = 'T207'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Create should fail on duplicate AC heading"
}

# --- Test 8: Changed AC on validate ---
It 'rejects validate when AC text changed in Issue' {
    $env = New-TestEnv
    $origBody = @"
# Test

## Canonical Acceptance Statement

Original AC text here.

## Requested Allowed Paths

scripts/governance/**
"@
    $issueFile = Join-Path $env.IssuesDir 'issue_8.json'
    Write-IssueJson -Path $issueFile -Body $origBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = '2222222222222222222222222222222222222222'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-08'
        IssueNumber = 8
        Driver = 'human'
        SpecTaskId = 'T207'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create should succeed"

    # Now change the issue body that gh returns
    $changedBody = @"
# Test

## Canonical Acceptance Statement

CHANGED: Original AC text here.

## Requested Allowed Paths

scripts/governance/**
"@
    $changedFile = Join-Path $env.IssuesDir 'issue_8_changed.json'
    Write-IssueJson -Path $changedFile -Body $changedBody -State 'open'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $changedFile

    $result2 = Invoke-Dispatch -Parameters @{
        ValidateDispatchId = 'req-064-test-20260712-08'
        ValidateIssueNumber = 8
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 1 -Message "Validate should fail on changed AC hash"
}

# --- Test 9: Path escape on create ---
It 'rejects create when dispatch path is outside Issue allowed paths' {
    $env = New-TestEnv
    $body = @"
# Test

## Canonical Acceptance Statement

AC content.

## Requested Allowed Paths

scripts/governance/**
"@
    $issueFile = Join-Path $env.IssuesDir 'issue_9.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = '3333333333333333333333333333333333333333'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-09'
        IssueNumber = 9
        Driver = 'human'
        SpecTaskId = 'T207'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('src/')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message "Create should reject path outside Issue scope"
}

# --- Test 10: Terminal reactivation rejection ---
It 'rejects supersede on an expired dispatch' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFile = Join-Path $env.IssuesDir 'issue_10.json'
    Write-IssueJson -Path $issueFile -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = '4444444444444444444444444444444444444444'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-10'
        IssueNumber = 10
        Driver = 'human'
        SpecTaskId = 'T207'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create should succeed"

    # Expire it
    $result2 = Invoke-Dispatch -Parameters @{
        ExpireDispatchId = 'req-064-test-20260712-10'
        ExpireIssueNumber = 10
        ExpirationReason = 'manual'
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 0 -Message "Expire should succeed"

    # Verify expired
    $dispatchFile = Join-Path $env.Store 'req-064-test-20260712-10.json'
    $content = Get-Content -LiteralPath $dispatchFile -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($content.state -eq 'expired') "State should be expired, got '$($content.state)'"

    # Try supersede on expired - should fail
    $result3 = Invoke-Dispatch -Parameters @{
        SupersedeDispatchId = 'req-064-test-20260712-10'
        SupersedeIssueNumber = 10
        SupersedeByDispatchId = 'req-064-test-20260712-11'
        SupersedeByDriver = 'codex'
        SupersedeBySpecTaskId = 'T207'
        SupersedeByGovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        SupersedeByAllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result3.ExitCode -Expected 1 -Message "Supersede on expired should fail"
}

# --- Test 11: Successful explicit Supersede ---
It 'explicitly supersedes the old dispatch and creates a fresh active dispatch' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFile = Join-Path $env.IssuesDir 'issue_11.json'
    Write-IssueJson -Path $issueFile -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = '5555555555555555555555555555555555555555'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    # Create v1
    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-41'
        IssueNumber = 11
        Driver = 'claude-code'
        SpecTaskId = 'T209'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create v1 should succeed"

    # Explicit Supersede supplies the full new envelope inputs.
    $result2 = Invoke-Dispatch -Parameters @{
        SupersedeDispatchId = 'req-064-test-20260712-41'
        SupersedeIssueNumber = 11
        SupersedeByDispatchId = 'req-064-test-20260712-42'
        SupersedeByDriver = 'human'
        SupersedeBySpecTaskId = 'T209'
        SupersedeByGovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        SupersedeByAllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 0 -Message "Explicit Supersede should succeed"

    # Verify v1 is superseded
    $v1File = Join-Path $env.Store 'req-064-test-20260712-41.json'
    $v1Content = Get-Content -LiteralPath $v1File -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($v1Content.state -eq 'superseded') "v1 should be superseded, got '$($v1Content.state)'"
    Assert-True ($v1Content.PSObject.Properties.Name -notcontains 'superseded_by') "Live envelopes must contain contract fields only"

    # Verify v2 is active
    $v2File = Join-Path $env.Store 'req-064-test-20260712-42.json'
    $v2Content = Get-Content -LiteralPath $v2File -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($v2Content.state -eq 'active') "v2 should be active"

    # Validate v2 should succeed
    $result3 = Invoke-Dispatch -Parameters @{
        ValidateDispatchId = 'req-064-test-20260712-42'
        ValidateIssueNumber = 11
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result3.ExitCode -Expected 0 -Message "Validate v2 should succeed"
}

# --- Test 12: Expire and Validate rejection ---
It 'rejects validate on an expired dispatch' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFile = Join-Path $env.IssuesDir 'issue_12.json'
    Write-IssueJson -Path $issueFile -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = '6666666666666666666666666666666666666666'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-12'
        IssueNumber = 12
        Driver = 'human'
        SpecTaskId = 'T209'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create should succeed"

    $result2 = Invoke-Dispatch -Parameters @{
        ExpireDispatchId = 'req-064-test-20260712-12'
        ExpireIssueNumber = 12
        ExpirationReason = 'base_sha_changed'
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 0 -Message "Expire should succeed"

    $result3 = Invoke-Dispatch -Parameters @{
        ValidateDispatchId = 'req-064-test-20260712-12'
        ValidateIssueNumber = 12
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result3.ExitCode -Expected 1 -Message "Validate on expired dispatch should fail"
}

# --- Test 13: Path escape on Validate ---
It 'rejects validate when Issue allowed paths no longer include dispatch paths' {
    $env = New-TestEnv
    $body = @"
# Test

## Canonical Acceptance Statement

AC content.

## Requested Allowed Paths

scripts/governance/**
docs/**
"@
    $issueFile = Join-Path $env.IssuesDir 'issue_13.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = '7777777777777777777777777777777777777777'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-13'
        IssueNumber = 13
        Driver = 'human'
        SpecTaskId = 'T209'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('docs/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create should succeed"

    # Restrict Issue paths
    $restrictedBody = @"
# Test

## Canonical Acceptance Statement

AC content.

## Requested Allowed Paths

scripts/governance/**
"@
    $restrictedFile = Join-Path $env.IssuesDir 'issue_13_restricted.json'
    Write-IssueJson -Path $restrictedFile -Body $restrictedBody -State 'open'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $restrictedFile

    $result2 = Invoke-Dispatch -Parameters @{
        ValidateDispatchId = 'req-064-test-20260712-13'
        ValidateIssueNumber = 13
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 1 -Message "Validate should fail on path escape"
}

# --- Test 14: Lock/atomicity cleanup ---
It 'cleans up lock files and temp files after successful create' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFile = Join-Path $env.IssuesDir 'issue_14.json'
    Write-IssueJson -Path $issueFile -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = '8888888888888888888888888888888888888888'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-14'
        IssueNumber = 14
        Driver = 'human'
        SpecTaskId = 'T209'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create should succeed"

    $lockFile = Join-Path $env.Store '.lock'
    Assert-True (-not (Test-Path -LiteralPath $lockFile)) "Lock file should be cleaned up"

    $tmpFiles = @(Get-ChildItem -LiteralPath $env.Store -Filter '*.tmp' -ErrorAction SilentlyContinue)
    Assert-True ($tmpFiles.Count -eq 0) "Temp files should be cleaned up, found $($tmpFiles.Count)"
}

# --- Test 15: Independent dispatches for different Issues ---
It 'creates independent dispatches for different Issues' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFileA = Join-Path $env.IssuesDir 'issue_15a.json'
    $issueFileB = Join-Path $env.IssuesDir 'issue_15b.json'
    Write-IssueJson -Path $issueFileA -Body $issueBody -State 'open'
    Write-IssueJson -Path $issueFileB -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = '9999999999999999999999999999999999999999'

    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFileA
    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-51'
        IssueNumber = 15
        Driver = 'human'
        SpecTaskId = 'T209'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "Create for Issue 15 should succeed"

    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFileB
    $result2 = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-52'
        IssueNumber = 16
        Driver = 'codex'
        SpecTaskId = 'T209'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 0 -Message "Create for Issue 16 should succeed (different Issue)"

    $fileA = Join-Path $env.Store 'req-064-test-20260712-51.json'
    $fileB = Join-Path $env.Store 'req-064-test-20260712-52.json'
    $contentA = Get-Content -LiteralPath $fileA -Raw -Encoding UTF8 | ConvertFrom-Json
    $contentB = Get-Content -LiteralPath $fileB -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($contentA.state -eq 'active') "Dispatch A should be active"
    Assert-True ($contentB.state -eq 'active') "Dispatch B should be active"
    Assert-True ($contentA.issue_number -eq 15) "Dispatch A issue_number mismatch"
    Assert-True ($contentB.issue_number -eq 16) "Dispatch B issue_number mismatch"
}

# --- Test 16: Duplicate dispatch_id ---
It 'rejects create when dispatch_id already exists' {
    $env = New-TestEnv
    $issueBody = Get-StandardAcBody
    $issueFile = Join-Path $env.IssuesDir 'issue_16.json'
    Write-IssueJson -Path $issueFile -Body $issueBody -State 'open'

    $env:INTERCRAFT_FAKE_MASTER_SHA = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile

    $result = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-16'
        IssueNumber = 16
        Driver = 'human'
        SpecTaskId = 'T209'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message "First create should succeed"

    # Same dispatch_id again (even for different Issue)
    $result2 = Invoke-Dispatch -Parameters @{
        DispatchId = 'req-064-test-20260712-16'
        IssueNumber = 17
        Driver = 'human'
        SpecTaskId = 'T209'
        GovernanceVersion = 'stage-a-owner-pr-bypass-v1'
        AllowedPath = @('scripts/governance/**')
        StorePath = $env.Store
    }
    Assert-ExitCode -Actual $result2.ExitCode -Expected 1 -Message "Duplicate dispatch_id should be rejected"
}

# --- Test 17: Requested Allowed Paths heading is mandatory ---
It 'fails closed when Requested Allowed Paths heading is missing' {
    $env = New-TestEnv
    $issueFile = Join-Path $env.IssuesDir 'issue_17.json'
    Write-IssueJson -Path $issueFile -Body "## Canonical Acceptance Statement`n`nA stable outcome." -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '1717171717171717171717171717171717171717'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-17'; IssueNumber=17; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message 'Missing path heading must fail closed'
}

# --- Test 18: Duplicate Requested Allowed Paths heading ---
It 'rejects duplicate Requested Allowed Paths headings' {
    $env = New-TestEnv
    $body = "## Canonical Acceptance Statement`n`nOutcome.`n`n## Requested Allowed Paths`n`nscripts/**`n`n## Requested Allowed Paths`n`ndocs/**"
    $issueFile = Join-Path $env.IssuesDir 'issue_18.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '1818181818181818181818181818181818181818'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-18'; IssueNumber=18; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message 'Duplicate path headings must fail closed'
}

# --- Test 19: Fenced headings are not Markdown headings ---
It 'ignores a fake AC heading inside a fenced code block' {
    $env = New-TestEnv
    $body = @'
```markdown
## Canonical Acceptance Statement
fake
```

## Canonical Acceptance Statement

Real stable outcome.

## Requested Allowed Paths

scripts/**
'@
    $issueFile = Join-Path $env.IssuesDir 'issue_19.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '1919191919191919191919191919191919191919'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-19'; IssueNumber=19; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message 'Fenced fake heading must be ignored'
}

# --- Test 20: Normalized-empty AC ---
It 'rejects AC content that is empty after normalization' {
    $env = New-TestEnv
    $body = "## Canonical Acceptance Statement`n`n   `n`t`n## Requested Allowed Paths`n`nscripts/**"
    $issueFile = Join-Path $env.IssuesDir 'issue_20.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '2020202020202020202020202020202020202020'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-20'; IssueNumber=20; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message 'Normalized-empty AC must fail closed'
}

# --- Test 21: Real hand-authored Issue path syntax ---
It 'accepts Markdown bullet paths with optional backticks' {
    $env = New-TestEnv
    $body = @'
## Canonical Acceptance Statement

Outcome.

## Requested Allowed Paths

- `.github/dispatches/**`
- `scripts/governance/dispatch.ps1`
'@
    $issueFile = Join-Path $env.IssuesDir 'issue_21.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '2121212121212121212121212121212121212121'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-21'; IssueNumber=21; Driver='codex'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('.github/dispatches/**','scripts/governance/dispatch.ps1'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message 'Markdown bullet/backtick paths should parse'
}

# --- Test 22: Corrupt live store ---
It 'fails closed when any live JSON file is corrupt' {
    $env = New-TestEnv
    $issueFile = Join-Path $env.IssuesDir 'issue_22.json'
    Write-IssueJson -Path $issueFile -Body (Get-StandardAcBody) -State 'open'
    Set-Content -LiteralPath (Join-Path $env.Store 'corrupt.json') -Value '{not-json' -Encoding ASCII
    $env:INTERCRAFT_FAKE_MASTER_SHA = '2222222222222222222222222222222222222222'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-22'; IssueNumber=22; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/governance/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message 'Corrupt store must block Create'
    Assert-True ((@($result.Output) -join "`n") -match 'DISPATCH_CORRUPT_STORE') 'Corrupt JSON must use the store-corruption error family'
    Assert-True (-not (Test-Path (Join-Path $env.Store 'req-064-test-20260712-22.json'))) 'Blocked Create must not write an envelope'
}

# --- Test 23: Governance version drift ---
It 'rejects a stored dispatch with governance version drift' {
    $env = New-TestEnv
    $issueFile = Join-Path $env.IssuesDir 'issue_23.json'
    Write-IssueJson -Path $issueFile -Body (Get-StandardAcBody) -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '2323232323232323232323232323232323232323'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $create = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-23'; IssueNumber=23; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/governance/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $create.ExitCode -Expected 0 -Message 'Create should succeed'
    $path = Join-Path $env.Store 'req-064-test-20260712-23.json'
    $dispatch = Get-Content -Raw -Encoding UTF8 $path | ConvertFrom-Json
    $dispatch.governance_version = 'obsolete-version'
    $dispatch | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $path -Encoding UTF8
    $validate = Invoke-Dispatch -Parameters @{ValidateDispatchId='req-064-test-20260712-23';ValidateIssueNumber=23;StorePath=$env.Store}
    Assert-ExitCode -Actual $validate.ExitCode -Expected 1 -Message 'Governance version drift must fail'
}

# --- Test 24: Unowned lock preservation ---
It 'does not delete a lock it failed to acquire' {
    $env = New-TestEnv
    $issueFile = Join-Path $env.IssuesDir 'issue_24.json'
    Write-IssueJson -Path $issueFile -Body (Get-StandardAcBody) -State 'open'
    $lock = Join-Path $env.Store '.lock'
    Set-Content -LiteralPath $lock -Value 'owned-by-another-process' -Encoding ASCII
    $env:INTERCRAFT_FAKE_MASTER_SHA = '2424242424242424242424242424242424242424'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-24'; IssueNumber=24; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/governance/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message 'Unowned lock must block Create'
    Assert-True (Test-Path -LiteralPath $lock) 'A process that did not acquire the lock must not delete it'
}

# --- Test 25: Crash artifact recovery ---
It 'fails closed and preserves an ambiguous temp artifact' {
    $env = New-TestEnv
    $issueFile = Join-Path $env.IssuesDir 'issue_25.json'
    Write-IssueJson -Path $issueFile -Body (Get-StandardAcBody) -State 'open'
    $artifact = Join-Path $env.Store 'old.json.deadbeef.tmp'
    Set-Content -LiteralPath $artifact -Value 'ambiguous' -Encoding ASCII
    $env:INTERCRAFT_FAKE_MASTER_SHA = '2525252525252525252525252525252525252525'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-25'; IssueNumber=25; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/governance/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message 'Ambiguous temp artifact must block Create'
    Assert-True (Test-Path -LiteralPath $artifact) 'Ambiguous recovery artifact must not be auto-deleted'
}

# --- Test 26: Deeper headings belong to canonical AC text ---
It 'includes deeper headings in the canonical AC hash' {
    $env = New-TestEnv
    $body = "## Canonical Acceptance Statement`n`nOutcome line.`n`n### Details`n`nMore detail.`n`n## Requested Allowed Paths`n`nscripts/**"
    $issueFile = Join-Path $env.IssuesDir 'issue_26.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '2626262626262626262626262626262626262626'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-26'; IssueNumber=26; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message 'Create should succeed'
    $dispatch = Get-Content -Raw -Encoding UTF8 (Join-Path $env.Store 'req-064-test-20260712-26.json') | ConvertFrom-Json
    # v1 trims each line and removes trailing blank lines, but intentionally
    # preserves the leading blank line between the Markdown heading and value.
    $canonical = "`nOutcome line.`n`n### Details`n`nMore detail."
    $bytes = (New-Object Text.UTF8Encoding $false).GetBytes($canonical)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $expected = ([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() } finally { $hasher.Dispose() }
    Assert-True ($dispatch.ac_hash -eq $expected) 'Deeper heading line was not included in canonical AC hash'
}

# --- Test 27: GitHub paths are case-sensitive ---
It 'rejects a case-only allowed-path mismatch' {
    $env = New-TestEnv
    $body = "## Canonical Acceptance Statement`n`nOutcome.`n`n## Requested Allowed Paths`n`nScripts/**"
    $issueFile = Join-Path $env.IssuesDir 'issue_27.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '2727272727272727272727272727272727272727'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-27'; IssueNumber=27; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message 'Case-only path mismatch must fail on GitHub semantics'
}

# --- Test 28: Authoritative response format ---
It 'rejects a malformed authoritative master SHA' {
    $env = New-TestEnv
    $issueFile = Join-Path $env.IssuesDir 'issue_28.json'
    Write-IssueJson -Path $issueFile -Body (Get-StandardAcBody) -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = 'not-a-commit-sha'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-28'; IssueNumber=28; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/governance/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message 'Malformed authoritative SHA must fail closed'
}

# --- Test 29: ATX closing hashes do not hide duplicates ---
It 'rejects a duplicate AC heading that uses closing hash syntax' {
    $env = New-TestEnv
    $body = "## Canonical Acceptance Statement`n`nFirst.`n`n## Canonical Acceptance Statement ##`n`nSecond.`n`n## Requested Allowed Paths`n`nscripts/**"
    $issueFile = Join-Path $env.IssuesDir 'issue_29.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '2929292929292929292929292929292929292929'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-29'; IssueNumber=29; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 1 -Message 'Closing hashes must not hide a duplicate canonical heading'
}

# --- Test 30: Indented code is not a heading ---
It 'ignores a heading-shaped line inside an indented code block' {
    $env = New-TestEnv
    $body = "    ## Canonical Acceptance Statement`n    fake`n`n## Canonical Acceptance Statement`n`nReal.`n`n## Requested Allowed Paths`n`nscripts/**"
    $issueFile = Join-Path $env.IssuesDir 'issue_30.json'
    Write-IssueJson -Path $issueFile -Body $body -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '3030303030303030303030303030303030303030'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $result = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-30'; IssueNumber=30; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $result.ExitCode -Expected 0 -Message 'Indented code must not count as a duplicate heading'
}

# --- Test 31: Issue identity is immutable during Expire ---
It 'rejects Expire when the caller supplies the wrong Issue number' {
    $env = New-TestEnv
    $issueFile = Join-Path $env.IssuesDir 'issue_31.json'
    Write-IssueJson -Path $issueFile -Body (Get-StandardAcBody) -State 'open'
    $env:INTERCRAFT_FAKE_MASTER_SHA = '3131313131313131313131313131313131313131'
    $env:INTERCRAFT_FAKE_ISSUE_PATH = $issueFile
    $create = Invoke-Dispatch -Parameters @{
        DispatchId='req-064-test-20260712-61'; IssueNumber=31; Driver='human'; SpecTaskId='T207'
        GovernanceVersion='stage-a-owner-pr-bypass-v1'; AllowedPath=@('scripts/governance/**'); StorePath=$env.Store
    }
    Assert-ExitCode -Actual $create.ExitCode -Expected 0 -Message 'Create should succeed'
    $expire = Invoke-Dispatch -Parameters @{
        ExpireDispatchId='req-064-test-20260712-61'; ExpireIssueNumber=32; ExpirationReason='manual'; StorePath=$env.Store
    }
    Assert-ExitCode -Actual $expire.ExitCode -Expected 1 -Message 'Wrong Issue identity must reject Expire'
    $dispatch = Get-Content -Raw -Encoding UTF8 (Join-Path $env.Store 'req-064-test-20260712-61.json') | ConvertFrom-Json
    Assert-True ($dispatch.state -eq 'active') 'Rejected Expire must leave the dispatch active'
}

# --- Test 32: Validate ID traversal is rejected before path resolution ---
It 'rejects a traversal ID for Validate without reading an external sentinel' {
    $env = New-TestEnv
    $sentinel = Join-Path $env.Root 'sentinel.json'
    Set-Content -LiteralPath $sentinel -Value '{"sentinel":"unchanged"}' -Encoding ASCII
    $before = [Convert]::ToBase64String([IO.File]::ReadAllBytes($sentinel))
    $rejected = $false
    try { & $scriptUnderTest -ValidateDispatchId '../sentinel' -ValidateIssueNumber 1 -StorePath $env.Store 2>&1 | Out-Null; $rejected = $LASTEXITCODE -ne 0 } catch { $rejected = $true }
    Assert-True $rejected 'Traversal Validate ID must be rejected'
    Assert-True (([Convert]::ToBase64String([IO.File]::ReadAllBytes($sentinel))) -eq $before) 'External sentinel changed'
}

# --- Test 33: Supersede old-ID traversal is rejected before path resolution ---
It 'rejects a traversal old ID for Supersede without mutating an external sentinel' {
    $env = New-TestEnv
    $sentinel = Join-Path $env.Root 'sentinel.json'
    Set-Content -LiteralPath $sentinel -Value '{"sentinel":"unchanged"}' -Encoding ASCII
    $before = [Convert]::ToBase64String([IO.File]::ReadAllBytes($sentinel))
    $rejected = $false
    try {
        & $scriptUnderTest -SupersedeDispatchId '../sentinel' -SupersedeIssueNumber 1 `
            -SupersedeByDispatchId 'req-064-test-20260712-71' -SupersedeByDriver codex `
            -SupersedeBySpecTaskId T207 -SupersedeByGovernanceVersion 'stage-a-owner-pr-bypass-v1' `
            -SupersedeByAllowedPath @('scripts/**') -StorePath $env.Store 2>&1 | Out-Null
        $rejected = $LASTEXITCODE -ne 0
    } catch { $rejected = $true }
    Assert-True $rejected 'Traversal Supersede ID must be rejected'
    Assert-True (([Convert]::ToBase64String([IO.File]::ReadAllBytes($sentinel))) -eq $before) 'External sentinel changed'
}

# --- Test 34: Expire ID traversal is rejected before path resolution ---
It 'rejects a traversal ID for Expire without mutating an external sentinel' {
    $env = New-TestEnv
    $sentinel = Join-Path $env.Root 'sentinel.json'
    Set-Content -LiteralPath $sentinel -Value '{"sentinel":"unchanged"}' -Encoding ASCII
    $before = [Convert]::ToBase64String([IO.File]::ReadAllBytes($sentinel))
    $rejected = $false
    try { & $scriptUnderTest -ExpireDispatchId '../sentinel' -ExpireIssueNumber 1 -ExpirationReason manual -StorePath $env.Store 2>&1 | Out-Null; $rejected = $LASTEXITCODE -ne 0 } catch { $rejected = $true }
    Assert-True $rejected 'Traversal Expire ID must be rejected'
    Assert-True (([Convert]::ToBase64String([IO.File]::ReadAllBytes($sentinel))) -eq $before) 'External sentinel changed'
}

# --- Test 35: Case-ambiguous IDs are rejected ---
It 'rejects uppercase dispatch IDs before filesystem access' {
    $env = New-TestEnv
    $rejected = $false
    try { & $scriptUnderTest -ValidateDispatchId 'REQ-064-test-20260712-72' -ValidateIssueNumber 1 -StorePath $env.Store 2>&1 | Out-Null; $rejected = $LASTEXITCODE -ne 0 } catch { $rejected = $true }
    Assert-True $rejected 'Uppercase/case-ambiguous dispatch ID must be rejected'
}

} finally {
    # Cleanup temp root
    $resolvedTemp = [IO.Path]::GetFullPath($tempRoot)
    $resolvedSystemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolvedTemp.StartsWith($resolvedSystemTemp, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolvedTemp -Leaf).StartsWith('intercraft-dispatch-test-', [StringComparison]::Ordinal)) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "RESULT passed=$script:passed failed=$script:failed"
if ($script:failed -gt 0) { exit 1 }
