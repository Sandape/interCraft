<#
.SYNOPSIS
    Read-only PR Gate for InterCraft delivery governance (Phase 6c).

.DESCRIPTION
    Validates a Pull Request against its dispatch envelope. Fails closed on
    any check failure. Invokes dispatch.ps1 -Validate as a child boundary for
    envelope integrity, then performs PR-specific checks.

    All reads go through authenticated `gh api` only. No GitHub writes, no
    stale origin/master, no authority-override parameters.

    Exit code 0 = all checks pass. Non-zero = first failure.

.PARAMETER PRNumber
    GitHub Pull Request number to validate.

.PARAMETER DispatchId
    Expected dispatch envelope ID for this PR's work.

.PARAMETER Owner
    GitHub repository owner (default: Sandape).

.PARAMETER Repo
    GitHub repository name (default: interCraft).

.EXAMPLE
    & gate.ps1 -PRNumber 42 -DispatchId 'req-064-feat-20260712-01'

.EXAMPLE
    & gate.ps1 -PRNumber 42 -DispatchId 'req-064-feat-20260712-01' `
        -Owner 'Sandape' -Repo 'interCraft'
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateRange(1, [int]::MaxValue)]
    [int] $PRNumber,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $DispatchId,

    [string] $Owner = 'Sandape',

    [string] $Repo = 'interCraft'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ======================================================================
# Constants
# ======================================================================
$GOVERNANCE_VERSION = 'stage-a-owner-pr-bypass-v1'
$MAX_PER_PAGE = 100
$MAX_PAGINATED_ITEMS = 10000
$DispatchScript = Join-Path $PSScriptRoot 'dispatch.ps1'
$StorePath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\.github\dispatches'))

# ======================================================================
# Helper: emit structured result and exit
# ======================================================================
function Exit-Gate {
    param(
        [bool] $Passed,
        [string] $FailedCheck = '',
        [string] $Message = ''
    )
    $result = @{
        passed = $Passed
    }
    if (-not $Passed) {
        $result.failed_check = $FailedCheck
        $result.message = $Message
    }
    Write-Output ($result | ConvertTo-Json -Compress)
    if ($Passed) { exit 0 } else { exit 1 }
}

# Validate before the identifier can participate in a filesystem path. Keep
# this inside the script (rather than a parameter attribute) so callers always
# receive the same structured JSON failure contract.
if ($DispatchId -cnotmatch '^[a-z0-9][a-z0-9._-]*$') {
    Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_REF_MALFORMED' `
        -Message "Dispatch ID '$DispatchId' is not a canonical safe identifier"
}

# ======================================================================
# Helper: gh api (read-only)
# ======================================================================
function Invoke-GhApi {
    <#
    .SYNOPSIS
        Calls gh api and returns the response text. Throws on non-zero exit
        or empty response. This is the single entry point for all gh calls.
    #>
    param([Parameter(Mandatory)][string[]] $ArgumentList)

    try {
        $allOutput = & gh @ArgumentList 2>&1
        $exitCode = $LASTEXITCODE
    } catch {
        Exit-Gate -Passed $false -FailedCheck 'GATE_TRANSPORT_FAILURE' `
            -Message "Unable to start gh: $($_.Exception.Message)"
    }

    if ($exitCode -ne 0) {
        $errorText = @($allOutput | ForEach-Object { "$_" }) -join "`n"
        Exit-Gate -Passed $false -FailedCheck 'GATE_TRANSPORT_FAILURE' `
            -Message "gh $($ArgumentList -join ' ') failed (exit $exitCode): $errorText"
    }

    $text = @($allOutput | Where-Object { $_ -is [string] }) -join "`n"
    if ([string]::IsNullOrWhiteSpace($text)) {
        Exit-Gate -Passed $false -FailedCheck 'GATE_TRANSPORT_FAILURE' `
            -Message "gh $($ArgumentList -join ' ') returned empty response"
    }

    return $text
}

# ======================================================================
# Helper: fetch paginated list via gh api
# ======================================================================
function Invoke-GhApiPagination {
    <#
    .SYNOPSIS
        Fetches a paginated GitHub list endpoint using --paginate and --jq '.[]'.
        Returns an array of parsed JSON objects.
        Fails closed on JSON parse errors or an explicit safety-cap breach.
        `gh api --paginate` follows GitHub Link headers until exhaustion, so
        exactly one full page is valid and is not treated as truncation.
    #>
    param([Parameter(Mandatory)][string[]] $BaseArgs)

    $fullArgs = $BaseArgs + @('--paginate', '--jq', '.[]')
    $outputLines = New-Object 'System.Collections.Generic.List[string]'
    $capExceeded = $false
    try {
        & gh @fullArgs 2>&1 | ForEach-Object {
            $outputLines.Add("$_")
            if ($outputLines.Count -gt $MAX_PAGINATED_ITEMS) {
                $capExceeded = $true
                throw 'GATE_INTERNAL_PAGINATION_CAP'
            }
        }
        $exitCode = $LASTEXITCODE
    } catch {
        if ($capExceeded) {
            Exit-Gate -Passed $false -FailedCheck 'GATE_PAGINATION_AMBIGUOUS' `
                -Message "Pagination exceeded the safety cap of $MAX_PAGINATED_ITEMS items"
        }
        Exit-Gate -Passed $false -FailedCheck 'GATE_TRANSPORT_FAILURE' `
            -Message "Unable to complete gh pagination: $($_.Exception.Message)"
    }
    $allOutput = $outputLines.ToArray()

    if ($exitCode -ne 0) {
        $errorText = @($allOutput | ForEach-Object { "$_" }) -join "`n"
        Exit-Gate -Passed $false -FailedCheck 'GATE_TRANSPORT_FAILURE' `
            -Message "gh $($fullArgs -join ' ') failed (exit $exitCode): $errorText"
    }

    # Ensure array — when a single line is returned, PowerShell gives us a scalar
    # string and foreach would iterate over characters.
    if ($allOutput -isnot [object[]]) {
        $allOutput = @($allOutput)
    }

    $results = New-Object 'System.Collections.Generic.List[PSObject]'
    foreach ($line in $allOutput) {
        $str = "$line"
        if ([string]::IsNullOrWhiteSpace($str)) { continue }
        try {
            $parsed = $str | ConvertFrom-Json
            if ($null -eq $parsed) {
                Exit-Gate -Passed $false -FailedCheck 'GATE_JSON_PARSE_FAILED' `
                    -Message 'Paginated response contained a null item'
            }
            $results.Add($parsed)
        } catch {
            Exit-Gate -Passed $false -FailedCheck 'GATE_JSON_PARSE_FAILED' `
                -Message "Failed to parse paginated response line: $str"
        }
    }

    return $results.ToArray()
}

# ======================================================================
# Helper: parse JSON response, fail on malformed
# ======================================================================
function ConvertFrom-JsonOrFail {
    param(
        [Parameter(Mandatory)][string] $Raw,
        [string] $Context = 'response'
    )
    try {
        return $Raw | ConvertFrom-Json
    } catch {
        Exit-Gate -Passed $false -FailedCheck 'GATE_JSON_PARSE_FAILED' `
            -Message ("Invalid JSON in $Context : $($_.Exception.Message)")
    }
}

function Assert-RequiredProperties {
    param(
        [AllowNull()] [object] $InputObject,
        [Parameter(Mandatory)] [string[]] $Names,
        [Parameter(Mandatory)] [string] $Context
    )

    if ($null -eq $InputObject) {
        Exit-Gate -Passed $false -FailedCheck 'GATE_JSON_PARSE_FAILED' `
            -Message "$Context is null"
    }
    foreach ($name in $Names) {
        if ($InputObject.PSObject.Properties.Name -notcontains $name) {
            Exit-Gate -Passed $false -FailedCheck 'GATE_JSON_PARSE_FAILED' `
                -Message "$Context is missing required property '$name'"
        }
    }
}

function Get-CodeFenceOpening {
    param([Parameter(Mandatory)] [AllowEmptyString()] [string] $Line)

    if ($Line -notmatch '^[ ]{0,3}(`{3,}|~{3,})(.*)$') { return $null }
    $marker = $matches[1]
    $info = $matches[2]
    # CommonMark forbids backticks in the info string of a backtick fence.
    if ($marker[0] -eq [char]96 -and $info.IndexOf([char]96) -ge 0) { return $null }
    return $marker
}

function Test-CodeFenceClosing {
    param(
        [Parameter(Mandatory)] [AllowEmptyString()] [string] $Line,
        [Parameter(Mandatory)] [char] $FenceCharacter,
        [Parameter(Mandatory)] [int] $FenceLength
    )

    $escapedCharacter = [regex]::Escape([string]$FenceCharacter)
    $pattern = '^[ ]{0,3}' + $escapedCharacter + '{' + $FenceLength + ',}[ \t]*$'
    return $Line -match $pattern
}

# ======================================================================
# Helper: validate repository-relative path (copied from dispatch.ps1)
# ======================================================================
function ConvertTo-RepositoryPath {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [switch] $AllowDirectoryGlob
    )

    $candidate = $Path.Trim().Replace('\', '/')
    while ($candidate.StartsWith('./', [StringComparison]::Ordinal)) {
        $candidate = $candidate.Substring(2)
    }

    # Reject control characters
    $hasControl = @($candidate.ToCharArray() | Where-Object {
        ([int]$_ -lt 32) -or ([int]$_ -eq 127)
    }).Count -gt 0

    if ([string]::IsNullOrWhiteSpace($candidate) -or
        $hasControl -or
        $candidate.Contains(':') -or
        [System.IO.Path]::IsPathRooted($candidate) -or
        $candidate -match '^[A-Za-z]:' -or
        $candidate.StartsWith('/', [StringComparison]::Ordinal)) {
        throw "GATE_PATH_ESCAPE: Path must be repository-relative: '$Path'"
    }

    # Check directory glob syntax
    $isDirGlob = $AllowDirectoryGlob -and $candidate.EndsWith('/**', [StringComparison]::Ordinal)
    $pathPortion = if ($isDirGlob) {
        $candidate.Substring(0, $candidate.Length - 3)
    } else {
        $candidate
    }

    if ($candidate.IndexOfAny([char[]]@('*', '?', '[', ']')) -ge 0 -and -not $isDirGlob) {
        throw "GATE_PATH_ESCAPE: Only an exact path or a trailing '/**' directory glob is allowed: '$Path'"
    }
    if ($isDirGlob -and $pathPortion.IndexOfAny([char[]]@('*', '?', '[', ']')) -ge 0) {
        throw "GATE_PATH_ESCAPE: Wildcards not allowed before trailing '/**': '$Path'"
    }

    # Check traversal and .git
    $segments = @($pathPortion.Split('/') | Where-Object { $_ -ne '' })
    $containsTraversal = @($segments | Where-Object { $_ -eq '.' -or $_ -eq '..' }).Count -gt 0
    $targetsGit = @($segments | Where-Object { $_.Equals('.git', [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0
    if ($segments.Count -eq 0 -or $containsTraversal -or $targetsGit) {
        throw "GATE_PATH_ESCAPE: Path traversal and .git metadata paths are forbidden: '$Path'"
    }

    $normalized = $segments -join '/'
    if ($isDirGlob) {
        return "$normalized/**"
    }
    return $normalized
}

function Assert-ChangedPathAllowed {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string[]] $AllowedPaths,
        [Parameter(Mandatory)] [string] $Role
    )

    try {
        $normalized = ConvertTo-RepositoryPath -Path $Path
    } catch {
        Exit-Gate -Passed $false -FailedCheck 'GATE_PATH_ESCAPE' `
            -Message "$Role '$Path' is not a safe repository path: $($_.Exception.Message)"
    }

    $matched = $false
    $caseOnlyMatch = $false
    foreach ($rule in $AllowedPaths) {
        if ($rule.EndsWith('/**', [StringComparison]::Ordinal)) {
            $prefix = $rule.Substring(0, $rule.Length - 3)
            if ($normalized.Equals($prefix, [StringComparison]::Ordinal) -or
                $normalized.StartsWith("$prefix/", [StringComparison]::Ordinal)) {
                $matched = $true
                break
            }
            if ($normalized.Equals($prefix, [StringComparison]::OrdinalIgnoreCase) -or
                $normalized.StartsWith("$prefix/", [StringComparison]::OrdinalIgnoreCase)) {
                $caseOnlyMatch = $true
            }
        }
        elseif ($normalized.Equals($rule, [StringComparison]::Ordinal)) {
            $matched = $true
            break
        }
        elseif ($normalized.Equals($rule, [StringComparison]::OrdinalIgnoreCase)) {
            $caseOnlyMatch = $true
        }
    }

    if (-not $matched) {
        if ($caseOnlyMatch) {
            Exit-Gate -Passed $false -FailedCheck 'GATE_PATH_ESCAPE' `
                -Message "$Role '$normalized' matches an allowed path only by case (case-sensitive paths required)"
        }
        Exit-Gate -Passed $false -FailedCheck 'GATE_PATH_ESCAPE' `
            -Message "$Role '$normalized' is not within allowed paths: $($AllowedPaths -join ', ')"
    }
}

# ======================================================================
# Helper: read dispatch envelope from disk (after dispatch.ps1 validates)
# ======================================================================
function Read-DispatchEnvelope {
    param([Parameter(Mandatory)] [string] $FilePath)

    if (-not [System.IO.File]::Exists($FilePath)) {
        Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_NOT_FOUND' `
            -Message "Dispatch file not found: $FilePath"
    }
    try {
        $raw = [System.IO.File]::ReadAllText($FilePath, [System.Text.Encoding]::UTF8)
        return $raw | ConvertFrom-Json
    } catch {
        Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_CORRUPT' `
            -Message "Failed to read or parse dispatch file '$FilePath': $($_.Exception.Message)"
    }
}

# ======================================================================
# Step 1: Fetch PR metadata
# ======================================================================
Write-Verbose "GATE: Fetching PR #$PRNumber metadata..."

$prRaw = Invoke-GhApi -ArgumentList @('api', "repos/$Owner/$Repo/pulls/$PRNumber")
$pr = ConvertFrom-JsonOrFail -Raw $prRaw -Context "PR #$PRNumber response"
Assert-RequiredProperties -InputObject $pr -Names @('number', 'state', 'base', 'head', 'body') -Context "PR #$PRNumber response"
Assert-RequiredProperties -InputObject $pr.base -Names @('ref', 'sha') -Context "PR #$PRNumber base"
Assert-RequiredProperties -InputObject $pr.head -Names @('sha') -Context "PR #$PRNumber head"

# Validate PR state is open
if ($pr.state -ne 'open') {
    Exit-Gate -Passed $false -FailedCheck 'GATE_INVALID_TARGET' `
        -Message "PR #$PRNumber is not open (state='$($pr.state)')"
}

# ======================================================================
# Step 2: Check PR targets master
# ======================================================================
Write-Verbose "GATE: Checking PR base ref..."

$baseRef = "$($pr.base.ref)"
if ($baseRef -cne 'master') {
    Exit-Gate -Passed $false -FailedCheck 'GATE_INVALID_TARGET' `
        -Message "PR targets '$baseRef', not 'master'"
}

$prBaseSha = "$($pr.base.sha)"
$prHeadSha = "$($pr.head.sha)"
if ($prBaseSha -cnotmatch '^[0-9a-f]{40}$' -or $prHeadSha -cnotmatch '^[0-9a-f]{40}$') {
    Exit-Gate -Passed $false -FailedCheck 'GATE_JSON_PARSE_FAILED' `
        -Message "PR base/head SHA is malformed (base='$prBaseSha', head='$prHeadSha')"
}

# ======================================================================
# Step 3: Parse Refs #N from PR body
# ======================================================================
Write-Verbose "GATE: Parsing Refs #N from PR body..."

$prBody = if ([string]::IsNullOrWhiteSpace($pr.body)) { '' } else { $pr.body }
$normalizedBody = $prBody -replace "`r`n", "`n" -replace "`r", "`n"
$bodyLines = $normalizedBody -split "`n"

$refsLines = New-Object 'System.Collections.Generic.List[string]'
$inRefsFence = $false
$refsFenceCharacter = [char]0
$refsFenceLength = 0
foreach ($line in $bodyLines) {
    if ($inRefsFence) {
        if (Test-CodeFenceClosing -Line $line -FenceCharacter $refsFenceCharacter -FenceLength $refsFenceLength) {
            $inRefsFence = $false
        }
        continue
    }
    $openingMarker = Get-CodeFenceOpening -Line $line
    if ($null -ne $openingMarker) {
        $inRefsFence = $true
        $refsFenceCharacter = $openingMarker[0]
        $refsFenceLength = $openingMarker.Length
        continue
    }
    # Four-space/tab-indented lines are Markdown code, not governance fields.
    if ($line -match '^[ ]{0,3}Refs[ \t]+#(\d+)[ \t]*$') {
        $refsLines.Add($matches[1])
    }
}

if ($refsLines.Count -eq 0) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_ISSUE_REF' `
        -Message "PR body does not contain 'Refs #N'"
}
if ($refsLines.Count -gt 1) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_ISSUE_REF' `
        -Message "PR body contains $($refsLines.Count) Refs entries (expected exactly 1): $($refsLines -join ', ')"
}

$issueNumber = 0
if (-not [int]::TryParse($refsLines[0], [ref]$issueNumber) -or $issueNumber -lt 1) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_ISSUE_REF' `
        -Message "PR Refs value must be a positive 32-bit Issue number"
}

# ======================================================================
# Step 4: Parse Dispatch ID from PR body ## Dispatch section
# ======================================================================
Write-Verbose "GATE: Parsing Dispatch ID from PR body..."

# Find exactly one Dispatch section and exactly one structured field.
$prDispatchValues = New-Object 'System.Collections.Generic.List[string]'
$dispatchHeadingCount = 0
$inDispatch = $false
$dispatchLevel = 0
$inDispatchFence = $false
$dispatchFenceCharacter = [char]0
$dispatchFenceLength = 0

for ($i = 0; $i -lt $bodyLines.Count; $i++) {
    $line = $bodyLines[$i]

    if ($inDispatchFence) {
        if (Test-CodeFenceClosing -Line $line -FenceCharacter $dispatchFenceCharacter -FenceLength $dispatchFenceLength) {
            $inDispatchFence = $false
        }
        continue
    }
    $openingMarker = Get-CodeFenceOpening -Line $line
    if ($null -ne $openingMarker) {
        $inDispatchFence = $true
        $dispatchFenceCharacter = $openingMarker[0]
        $dispatchFenceLength = $openingMarker.Length
        continue
    }

    if ($line -match '^[ ]{0,3}(#{1,6})[ \t]+(.+?)\s*$') {
        $level = $matches[1].Length
        $text = ($matches[2].Trim() -replace '[ \t]+#+[ \t]*$', '').Trim()

        if ($text -eq 'Dispatch' -and $level -eq 2) {
            $dispatchHeadingCount++
            $inDispatch = $true
            $dispatchLevel = $level
            continue
        }

        if ($inDispatch -and $level -le $dispatchLevel) {
            # Continue scanning after this section so a later duplicate
            # Dispatch heading cannot be hidden behind another peer heading.
            $inDispatch = $false
        }
        continue
    }

    if ($inDispatch) {
        if ($line -match '^[ ]{0,3}[-*]\s+\*\*Dispatch ID\*\*:\s*`?([^`]+?)`?\s*$') {
            $prDispatchValues.Add($matches[1].Trim())
        }
    }
}

if ($dispatchHeadingCount -ne 1 -or $prDispatchValues.Count -ne 1) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_REF_MALFORMED' `
        -Message "PR body must contain exactly one Dispatch heading and one structured Dispatch ID field; found headings=$dispatchHeadingCount fields=$($prDispatchValues.Count)"
}
$prDispatchFieldValue = $prDispatchValues[0]

# Verify the PR's Dispatch ID matches the requested dispatch
if ($prDispatchFieldValue -cne $DispatchId) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_REF_MALFORMED' `
        -Message "PR Dispatch ID '$prDispatchFieldValue' does not match expected '$DispatchId'"
}

# ======================================================================
# Step 5: Fetch Issue #N and verify it's open
# ======================================================================
Write-Verbose "GATE: Fetching Issue #$issueNumber..."
$issueRaw = Invoke-GhApi -ArgumentList @('api', "repos/$Owner/$Repo/issues/$issueNumber")
$issue = ConvertFrom-JsonOrFail -Raw $issueRaw -Context "Issue #$issueNumber response"
Assert-RequiredProperties -InputObject $issue -Names @('state') -Context "Issue #$issueNumber response"
if ($issue.PSObject.Properties.Name -contains 'pull_request') {
    Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_ISSUE_REF' `
        -Message "Refs #$issueNumber resolves to a Pull Request, not a governance Issue"
}

if ($issue.state -ne 'open') {
    Exit-Gate -Passed $false -FailedCheck 'GATE_ISSUE_NOT_OPEN' `
        -Message "Issue #$issueNumber is not open (state='$($issue.state)')"
}

# ======================================================================
# Step 6: Invoke dispatch.ps1 Validate (child boundary)
# ======================================================================
Write-Verbose "GATE: Invoking dispatch.ps1 Validate for '$DispatchId', Issue #$issueNumber..."

$storeDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($StorePath)
$dispatchFile = [System.IO.Path]::Combine($storeDir, "$DispatchId.json")
if (-not [System.IO.File]::Exists($dispatchFile)) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_NOT_FOUND' `
        -Message "Dispatch file not found: $dispatchFile"
}

# Call dispatch.ps1 Validate as a child process. This validates the
# envelope against current authoritative master and Issue state. GitHub
# Actions uses PowerShell 7 (`pwsh`) on Linux, while Windows developers may
# have either `pwsh` or Windows PowerShell (`powershell.exe`). Resolve the
# host from PATH instead of assuming the Windows-only PSHOME layout.
$childHost = @('pwsh', 'powershell.exe') |
    ForEach-Object {
        Get-Command -Name $_ -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
    } |
    Select-Object -First 1
if ($null -eq $childHost) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_VALIDATION_FAILED' `
        -Message 'No supported PowerShell child host found (expected pwsh or powershell.exe)'
}
$powershellExe = $childHost.Source
$previousErrorAction = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    $dispatchValidateOutput = & $powershellExe -NoProfile -File $DispatchScript `
        -ValidateDispatchId $DispatchId `
        -ValidateIssueNumber $issueNumber `
        -StorePath $StorePath `
        -Owner $Owner `
        -Repo $Repo 2>&1
    $dispatchExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorAction
}

if ($dispatchExitCode -ne 0) {
    $errorMsg = @($dispatchValidateOutput | ForEach-Object { "$_" } | Where-Object { $_ -match 'ERROR:' }) -join '; '
    if ([string]::IsNullOrWhiteSpace($errorMsg)) {
        $errorMsg = @($dispatchValidateOutput | ForEach-Object { "$_" }) -join '; '
    }

    # Map dispatch errors to gate error codes
    if ($errorMsg -match 'DISPATCH_NOT_FOUND') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_NOT_FOUND' `
            -Message "Dispatch '$DispatchId' not found: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_INACTIVE') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_INACTIVE' `
            -Message "Dispatch '$DispatchId' is inactive: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_ISSUE_MISMATCH') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_ISSUE_REF' `
            -Message "Dispatch Issue mismatch: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_ISSUE_INVALID') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_ISSUE_REF' `
            -Message "Dispatch does not reference a valid governance Issue: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_INVALID_GOVERNANCE_VERSION') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_GOV_VERSION_MISMATCH' `
            -Message "Governance version mismatch: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_AC_HASH_MISMATCH') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_AC_HASH_MISMATCH' `
            -Message "AC hash mismatch: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_BASE_STALE') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_BASE_NOT_AUTHORITATIVE' `
            -Message "Base SHA stale: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_ISSUE_CLOSED') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_ISSUE_NOT_OPEN' `
            -Message "Issue closed: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_PATH_ESCAPE') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_PATH_ESCAPE' `
            -Message "Path escape in dispatch validation: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_DUPLICATE_ACTIVE') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_DUPLICATE_PR' `
            -Message "Duplicate active dispatch: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_CORRUPT_STORE') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_CORRUPT' `
            -Message "Corrupt dispatch store: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_RECOVERY_REQUIRED' -or $errorMsg -match 'DISPATCH_LOCK_FAILED') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_CORRUPT' `
            -Message "Dispatch store requires explicit recovery: $errorMsg"
    } elseif ($errorMsg -match 'AC_MALFORMED' -or $errorMsg -match 'PATHS_MALFORMED') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_AC_MALFORMED' `
            -Message "AC or paths malformed in Issue: $errorMsg"
    } elseif ($errorMsg -match 'DISPATCH_GH_API_FAILED') {
        Exit-Gate -Passed $false -FailedCheck 'GATE_TRANSPORT_FAILURE' `
            -Message "gh api failed during dispatch validation: $errorMsg"
    } else {
        Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_VALIDATION_FAILED' `
            -Message "Dispatch validation failed for '$DispatchId': $errorMsg"
    }
}

# ======================================================================
# Step 7: Read validated envelope from disk
# ======================================================================
Write-Verbose "GATE: Reading validated envelope..."
$envelope = Read-DispatchEnvelope -FilePath $dispatchFile
Assert-RequiredProperties -InputObject $envelope `
    -Names @('issue_number', 'state', 'allowed_paths', 'base_sha') `
    -Context "Dispatch '$DispatchId' envelope"

# Double-check envelope issue_number matches Refs #N
if ([int]$envelope.issue_number -ne $issueNumber) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_ISSUE_REF' `
        -Message "Envelope issue_number ($($envelope.issue_number)) does not match PR Refs #$issueNumber"
}

# Double-check envelope is active
if ("$($envelope.state)" -cne 'active') {
    Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_INACTIVE' `
        -Message "Envelope state is '$($envelope.state)', expected 'active'"
}

# Record allowed paths from envelope
$allowedPaths = @($envelope.allowed_paths)

# ======================================================================
# Step 8: Fetch authoritative master SHA
# ======================================================================
Write-Verbose "GATE: Fetching authoritative master SHA..."
$masterRaw = Invoke-GhApi -ArgumentList @('api', "repos/$Owner/$Repo/git/ref/heads/master")
$masterRef = ConvertFrom-JsonOrFail -Raw $masterRaw -Context 'master ref response'
Assert-RequiredProperties -InputObject $masterRef -Names @('object') -Context 'master ref response'
Assert-RequiredProperties -InputObject $masterRef.object -Names @('sha') -Context 'master ref object'

$authMasterSha = "$($masterRef.object.sha)"
if ($authMasterSha -cnotmatch '^[0-9a-f]{40}$') {
    Exit-Gate -Passed $false -FailedCheck 'GATE_TRANSPORT_FAILURE' `
        -Message "Authoritative master SHA is malformed: '$authMasterSha'"
}

# ======================================================================
# Step 9: Base freshness — envelope base_sha == authoritative master
# ======================================================================
Write-Verbose "GATE: Checking base freshness..."
$envelopeBaseSha = "$($envelope.base_sha)"

if ($authMasterSha -cne $envelopeBaseSha) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_BASE_NOT_AUTHORITATIVE' `
        -Message "Envelope base SHA '$envelopeBaseSha' does not equal authoritative master '$authMasterSha'"
}

# ======================================================================
# Step 10: PR base SHA matches envelope base
# ======================================================================
Write-Verbose "GATE: Checking PR base SHA..."
if ($prBaseSha -cne $envelopeBaseSha) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_BASE_STALE' `
        -Message "PR base SHA '$prBaseSha' does not match envelope base SHA '$envelopeBaseSha'"
}

# ======================================================================
# Step 11: Ancestry check — PR head descends from base
# ======================================================================
Write-Verbose "GATE: Checking PR ancestry via compare API..."
$compareRaw = Invoke-GhApi -ArgumentList @('api', "repos/$Owner/$Repo/compare/$envelopeBaseSha...$prHeadSha")

$compare = ConvertFrom-JsonOrFail -Raw $compareRaw -Context 'compare response'
Assert-RequiredProperties -InputObject $compare -Names @('status') -Context 'compare response'

$status = "$($compare.status)"
if (@('ahead', 'identical') -cnotcontains $status) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_BASE_STALE' `
        -Message "PR head does not descend from base (compare status='$status'). Rebase required."
}
$mergeBaseSha = ''
if ($compare.PSObject.Properties.Name -contains 'merge_base_commit' -and $null -ne $compare.merge_base_commit) {
    Assert-RequiredProperties -InputObject $compare.merge_base_commit -Names @('sha') -Context 'compare merge_base_commit'
    $mergeBaseSha = "$($compare.merge_base_commit.sha)"
}
if (-not [string]::IsNullOrWhiteSpace($mergeBaseSha) -and $mergeBaseSha -cne $envelopeBaseSha) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_BASE_STALE' `
        -Message "Compare API merge base '$mergeBaseSha' does not equal dispatch base '$envelopeBaseSha'"
}

# ======================================================================
# Step 12: Fetch PR files and validate paths
# ======================================================================
Write-Verbose "GATE: Fetching PR files..."
$prFilesPath = "repos/$Owner/$Repo/pulls/$PRNumber/files?per_page=$MAX_PER_PAGE"

# Use paginated fetch for PR files
$prFiles = @(Invoke-GhApiPagination -BaseArgs @('api', $prFilesPath))

if ($prFiles.Count -eq 0) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_PATH_ESCAPE' `
        -Message "PR #$PRNumber has no changed files"
}

# Validate each changed file path
foreach ($file in $prFiles) {
    Assert-RequiredProperties -InputObject $file -Names @('filename', 'status') -Context 'PR file entry'
    $filename = "$($file.filename)"
    if ([string]::IsNullOrWhiteSpace($filename)) {
        Exit-Gate -Passed $false -FailedCheck 'GATE_PATH_ESCAPE' `
            -Message "PR file entry has empty or missing filename"
    }
    Assert-ChangedPathAllowed -Path $filename -AllowedPaths $allowedPaths -Role 'PR destination path'

    if ("$($file.status)" -ceq 'renamed') {
        Assert-RequiredProperties -InputObject $file -Names @('previous_filename') -Context 'Renamed PR file entry'
        $previousFilename = "$($file.previous_filename)"
        if ([string]::IsNullOrWhiteSpace($previousFilename)) {
            Exit-Gate -Passed $false -FailedCheck 'GATE_PATH_ESCAPE' `
                -Message 'Renamed PR file entry has empty previous_filename'
        }
        # A rename changes both repository paths. Validate the source as well
        # as the destination so an out-of-scope delete/move cannot hide behind
        # an in-scope destination.
        Assert-ChangedPathAllowed -Path $previousFilename -AllowedPaths $allowedPaths -Role 'PR rename source path'
    }
}

# ======================================================================
# Step 13: Singleton / Consumption check
# ======================================================================
Write-Verbose "GATE: Checking dispatch singleton and consumption..."
$allPrsPath = "repos/$Owner/$Repo/pulls?state=all"
$allPrs = @(Invoke-GhApiPagination -BaseArgs @('api', $allPrsPath))

$foundCurrent = $false
$foundOtherOpen = $false
$foundConsumed = $false
$consumedInfo = ''

foreach ($otherPr in $allPrs) {
    foreach ($requiredProperty in @('number', 'state', 'body')) {
        if ($otherPr.PSObject.Properties.Name -notcontains $requiredProperty) {
            Exit-Gate -Passed $false -FailedCheck 'GATE_JSON_PARSE_FAILED' `
                -Message "Paginated PR entry is missing required property '$requiredProperty'"
        }
    }
    $otherNumber = $otherPr.number
    $otherTitle = if ($otherPr.PSObject.Properties.Name -contains 'title' -and $otherPr.title) { $otherPr.title } else { "(no title)" }
    $otherBody = if ([string]::IsNullOrWhiteSpace($otherPr.body)) { '' } else { $otherPr.body }
    $otherState = "$($otherPr.state)"

    # Parse other PR body for the same Dispatch ID field
    $otherNormalized = $otherBody -replace "`r`n", "`n" -replace "`r", "`n"
    $otherLines = $otherNormalized -split "`n"
    $otherDispatchIds = New-Object 'System.Collections.Generic.List[string]'
    $inOtherFence = $false
    $otherFenceCharacter = [char]0
    $otherFenceLength = 0
    foreach ($l in $otherLines) {
        if ($inOtherFence) {
            if (Test-CodeFenceClosing -Line $l -FenceCharacter $otherFenceCharacter -FenceLength $otherFenceLength) {
                $inOtherFence = $false
            }
            continue
        }
        $openingMarker = Get-CodeFenceOpening -Line $l
        if ($null -ne $openingMarker) {
            $inOtherFence = $true
            $otherFenceCharacter = $openingMarker[0]
            $otherFenceLength = $openingMarker.Length
            continue
        }
        if ($l -match '^[ ]{0,3}[-*]?\s*\*\*Dispatch ID\*\*:\s*`?([^`]+?)`?\s*$') {
            $otherDispatchIds.Add($matches[1].Trim())
        }
    }

    if ($otherDispatchIds -cnotcontains $DispatchId) { continue }

    if ($otherNumber -eq $PRNumber) {
        $foundCurrent = $true
        continue
    }

    # This is another PR referencing the same dispatch
    if ($otherState -eq 'open') {
        $foundOtherOpen = $true
        $consumedInfo = "Open PR #$otherNumber '$otherTitle' also references dispatch '$DispatchId'"
        break
    }

    # closed or merged = consumed
    $foundConsumed = $true
    $consumedInfo = "PR #$otherNumber ($otherState) already consumed dispatch '$DispatchId'"
}

if (-not $foundCurrent) {
    # This shouldn't happen since we fetched the PR itself, but be defensive
    Exit-Gate -Passed $false -FailedCheck 'GATE_DISPATCH_NOT_FOUND' `
        -Message "Current PR #$PRNumber not found in PR enumeration"
}

if ($foundOtherOpen) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_DUPLICATE_PR' `
        -Message "Singleton violation: $consumedInfo"
}

if ($foundConsumed) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_DUPLICATE_PR' `
        -Message "Dispatch already consumed: $consumedInfo"
}

# ======================================================================
# Step 14: Evidence check
# ======================================================================
Write-Verbose "GATE: Checking Evidence section..."

# Reuse body parsing to find ## Evidence heading
$evidenceFound = $false
$evidenceHeadingCount = 0
$evidenceLevel = 0
$inEvidence = $false
$evidenceContent = New-Object 'System.Collections.Generic.List[string]'
$inCodeFence = $false
$fenceChar = [char]0
$fenceLen = 0

for ($i = 0; $i -lt $bodyLines.Count; $i++) {
    $line = $bodyLines[$i]

    # Code fence tracking follows CommonMark closing-fence rules: the closing
    # line may contain only the marker and trailing whitespace.
    if ($inCodeFence) {
        if (Test-CodeFenceClosing -Line $line -FenceCharacter $fenceChar -FenceLength $fenceLen) {
            $inCodeFence = $false
            $fenceChar = [char]0
            $fenceLen = 0
            continue
        }
        if ($inEvidence) { $evidenceContent.Add($line) }
        continue
    }
    $openingMarker = Get-CodeFenceOpening -Line $line
    if ($null -ne $openingMarker) {
        $inCodeFence = $true
        $fenceChar = $openingMarker[0]
        $fenceLen = $openingMarker.Length
        continue
    }

    if ($line -match '^[ ]{0,3}(#{1,6})[ \t]+(.+?)\s*$') {
        $level = $matches[1].Length
        $text = ($matches[2].Trim() -replace '[ \t]+#+[ \t]*$', '').Trim()

        if ($text -eq 'Evidence' -and $level -eq 2) {
            $evidenceHeadingCount++
            if ($evidenceHeadingCount -gt 1) {
                Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_EVIDENCE' `
                    -Message 'PR body contains duplicate Evidence headings'
            }
            $evidenceFound = $true
            $evidenceLevel = $level
            $inEvidence = $true
            continue
        }

        if ($inEvidence -and $level -le $evidenceLevel) {
            # End content collection for the first Evidence section, but keep
            # scanning the full body so a later duplicate heading cannot hide
            # behind an intervening peer section.
            $inEvidence = $false
        }
        continue
    }

    if ($inEvidence) {
        $evidenceContent.Add($line)
    }
}

if (-not $evidenceFound) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_EVIDENCE' `
        -Message "PR body does not contain a '## Evidence' section"
}

$evidenceText = $evidenceContent.ToArray() -join "`n"
$evidenceWithoutComments = [regex]::Replace($evidenceText, '<!--.*?-->', '', [Text.RegularExpressions.RegexOptions]::Singleline)
$evidenceNormalized = $evidenceWithoutComments.Trim()
$placeholderOnly = $evidenceNormalized -match '(?is)^\s*(?:[-*]\s*)?(?:\[[ xX]\]\s*)?(?:tbd|todo|pending|placeholder|none|n/?a|not yet)(?:[\s.!-]*)$'
if ([string]::IsNullOrWhiteSpace($evidenceNormalized) -or $placeholderOnly) {
    Exit-Gate -Passed $false -FailedCheck 'GATE_MISSING_EVIDENCE' `
        -Message "Evidence section has no substantive content after removing comments, whitespace, and placeholder-only text"
}

# ======================================================================
# All checks passed
# ======================================================================
Write-Verbose "GATE: All checks passed"
Exit-Gate -Passed $true
