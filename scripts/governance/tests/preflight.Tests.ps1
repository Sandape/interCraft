[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptUnderTest = Join-Path $PSScriptRoot '..\preflight.ps1'
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("intercraft-governance-preflight-{0}" -f [guid]::NewGuid().ToString('N'))
$script:passed = 0
$script:failed = 0

function Invoke-Git {
    param(
        [Parameter(Mandatory)]
        [string] $Repository,

        [Parameter(Mandatory)]
        [string[]] $Arguments
    )

    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & git -C $Repository @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    if ($exitCode -ne 0) {
        throw "git $($Arguments -join ' ') failed: $($output -join [Environment]::NewLine)"
    }
    return $output
}

function New-TestRepository {
    $repository = Join-Path $tempRoot ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $repository -Force | Out-Null
    & git init -b master $repository 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'git init failed'
    }

    Invoke-Git -Repository $repository -Arguments @('config', 'user.name', 'Governance Test') | Out-Null
    Invoke-Git -Repository $repository -Arguments @('config', 'user.email', 'governance-test@example.invalid') | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $repository 'scripts/governance') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $repository 'README.md') -Value "fixture`n" -Encoding UTF8
    Invoke-Git -Repository $repository -Arguments @('add', 'README.md') | Out-Null
    Invoke-Git -Repository $repository -Arguments @('commit', '-m', 'test: initialize fixture') | Out-Null
    $baseSha = (Invoke-Git -Repository $repository -Arguments @('rev-parse', 'HEAD') | Select-Object -Last 1).Trim()
    Invoke-Git -Repository $repository -Arguments @('update-ref', 'refs/remotes/origin/master', $baseSha) | Out-Null
    Invoke-Git -Repository $repository -Arguments @('switch', '-c', 'codex/test-preflight') | Out-Null

    return [pscustomobject]@{
        Root = $repository
        BaseSha = $baseSha
        Branch = 'codex/test-preflight'
    }
}

function Invoke-Preflight {
    param(
        [Parameter(Mandatory)]
        [pscustomobject] $Fixture,

        [string] $ExpectedRoot = $Fixture.Root,
        [string] $ExpectedBranch = $Fixture.Branch,
        [string] $ExpectedBaseSha = $Fixture.BaseSha,
        [string[]] $AllowedPath = @('scripts/governance/**'),
        [string[]] $TargetPath = @('scripts/governance/preflight.ps1'),
        [switch] $AllowDirtyWithinAllowedPaths
    )

    $parameters = @{
        ExpectedRepoRoot = $ExpectedRoot
        ExpectedBranch = $ExpectedBranch
        ExpectedBaseSha = $ExpectedBaseSha
        BaseRef = 'origin/master'
        AllowedPath = $AllowedPath
        TargetPath = $TargetPath
        OutputJson = $true
    }
    if ($AllowDirtyWithinAllowedPaths) {
        $parameters.AllowDirtyWithinAllowedPaths = $true
    }

    Push-Location $Fixture.Root
    try {
        $output = & $scriptUnderTest @parameters 2>&1
        return [pscustomobject]@{
            Succeeded = $true
            Text = ($output -join [Environment]::NewLine)
        }
    }
    catch {
        return [pscustomobject]@{
            Succeeded = $false
            Text = $_.Exception.Message
        }
    }
    finally {
        Pop-Location
    }
}

function It {
    param(
        [Parameter(Mandatory)]
        [string] $Name,

        [Parameter(Mandatory)]
        [scriptblock] $Test
    )

    try {
        & $Test
        $script:passed++
        Write-Host "PASS $Name"
    }
    catch {
        $script:failed++
        Write-Host "FAIL $Name :: $($_.Exception.Message)"
    }
}

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) {
        throw $Message
    }
}

function Assert-ErrorCode {
    param([pscustomobject] $Result, [string] $Code)
    Assert-True (-not $Result.Succeeded) "Expected failure $Code, but preflight succeeded"
    Assert-True ($Result.Text -like "*PREFLIGHT_FAILED:${Code}:*") "Expected $Code, got: $($Result.Text)"
}

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    It 'passes for the expected clean worktree, branch, base, and allowed target' {
        $fixture = New-TestRepository
        $result = Invoke-Preflight -Fixture $fixture
        Assert-True $result.Succeeded "Expected success, got: $($result.Text)"
        Assert-True ($result.Text -like '*"ok":true*') "Expected JSON success payload, got: $($result.Text)"
    }

    It 'rejects running from a different repository root' {
        $fixture = New-TestRepository
        $wrongRoot = Join-Path $tempRoot 'not-the-repository'
        $result = Invoke-Preflight -Fixture $fixture -ExpectedRoot $wrongRoot
        Assert-ErrorCode -Result $result -Code 'REPO_ROOT_MISMATCH'
    }

    It 'rejects master and any unexpected branch' {
        $fixture = New-TestRepository
        $result = Invoke-Preflight -Fixture $fixture -ExpectedBranch 'codex/another-dispatch'
        Assert-ErrorCode -Result $result -Code 'BRANCH_MISMATCH'
    }

    It 'rejects a stale or incorrect base SHA' {
        $fixture = New-TestRepository
        $result = Invoke-Preflight -Fixture $fixture -ExpectedBaseSha ('0' * 40)
        Assert-ErrorCode -Result $result -Code 'BASE_SHA_MISMATCH'
    }

    It 'rejects a dirty worktree by default' {
        $fixture = New-TestRepository
        Set-Content -LiteralPath (Join-Path $fixture.Root 'scripts/governance/new-file.txt') -Value 'dirty' -Encoding UTF8
        $result = Invoke-Preflight -Fixture $fixture
        Assert-ErrorCode -Result $result -Code 'DIRTY_WORKTREE'
    }

    It 'allows dirty paths only when every dirty path is inside the allowlist' {
        $fixture = New-TestRepository
        Set-Content -LiteralPath (Join-Path $fixture.Root 'scripts/governance/new-file.txt') -Value 'dirty' -Encoding UTF8
        $result = Invoke-Preflight -Fixture $fixture -AllowDirtyWithinAllowedPaths
        Assert-True $result.Succeeded "Expected allowed dirty path to pass, got: $($result.Text)"
    }

    It 'rejects a dirty path outside the allowlist even in scoped dirty mode' {
        $fixture = New-TestRepository
        Set-Content -LiteralPath (Join-Path $fixture.Root 'outside.txt') -Value 'dirty' -Encoding UTF8
        $result = Invoke-Preflight -Fixture $fixture -AllowDirtyWithinAllowedPaths
        Assert-ErrorCode -Result $result -Code 'DIRTY_PATH_ESCAPE'
    }

    It 'rejects target path traversal' {
        $fixture = New-TestRepository
        $result = Invoke-Preflight -Fixture $fixture -TargetPath '../outside.txt'
        Assert-ErrorCode -Result $result -Code 'INVALID_TARGET_PATH'
    }

    It 'rejects targets outside the dispatch allowlist' {
        $fixture = New-TestRepository
        $result = Invoke-Preflight -Fixture $fixture -TargetPath 'backend/app/main.py'
        Assert-ErrorCode -Result $result -Code 'TARGET_NOT_ALLOWED'
    }

    It 'rejects unsupported wildcard syntax in allowed paths' {
        $fixture = New-TestRepository
        $result = Invoke-Preflight -Fixture $fixture -AllowedPath 'scripts/*/preflight.ps1'
        Assert-ErrorCode -Result $result -Code 'INVALID_ALLOWED_PATH'
    }

    It 'rejects Windows alternate-data-stream target syntax' {
        $fixture = New-TestRepository
        $result = Invoke-Preflight -Fixture $fixture -TargetPath 'scripts/governance/preflight.ps1:payload'
        Assert-ErrorCode -Result $result -Code 'INVALID_TARGET_PATH'
    }

    It 'rejects Git metadata targets even when a dispatch allowlists them' {
        $fixture = New-TestRepository
        $result = Invoke-Preflight -Fixture $fixture -AllowedPath '.git/**' -TargetPath '.git/config'
        Assert-ErrorCode -Result $result -Code 'INVALID_ALLOWED_PATH'
    }

    It 'rejects control characters in target paths' {
        $fixture = New-TestRepository
        $result = Invoke-Preflight -Fixture $fixture -TargetPath "scripts/governance/preflight.ps1`nother"
        Assert-ErrorCode -Result $result -Code 'INVALID_TARGET_PATH'
    }
}
finally {
    $resolvedTemp = [IO.Path]::GetFullPath($tempRoot)
    $resolvedSystemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolvedTemp.StartsWith($resolvedSystemTemp, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolvedTemp -Leaf).StartsWith('intercraft-governance-preflight-', [StringComparison]::Ordinal)) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "RESULT passed=$script:passed failed=$script:failed"
if ($script:failed -gt 0) {
    exit 1
}
