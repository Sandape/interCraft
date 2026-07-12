<#
.SYNOPSIS
    Dispatch state machine for InterCraft delivery governance.

.DESCRIPTION
    Creates, validates, supersedes, and expires dispatch envelopes stored
    as JSON files under .github/dispatches/. Each dispatch authorizes one
    execution unit of governance or feature work.

    Operations (parameter sets):
      Create    — Create a new dispatch envelope after validating base SHA,
                  Issue AC text, and allowed paths via gh api. REJECTS if any
                  active dispatch already exists for the same Issue.
      Validate  — Re-fetch authoritative master and Issue, then validate
                  the dispatch against current state.
      Supersede — Mark an active dispatch as superseded by a new dispatch,
                  requiring complete new dispatch data. Conservative crash
                  order: old terminal first, then new active.
      Expire    — Mark an active dispatch as expired (base/AC divergence).

.PARAMETER DispatchId
    Unique dispatch identifier for Create, format:
    <req-prefix>-<purpose>-<yyyymmdd>-<nn>

.PARAMETER IssueNumber
    GitHub Issue number for Create.

.PARAMETER Driver
    Actor executing the work: claude-code, codex, cursor, cursor-automation,
    or human.

.PARAMETER SpecTaskId
    Reference to canonical spec or task ID (e.g. REQ-064, T101).

.PARAMETER GovernanceVersion
    Active governance system version. Must equal the current version
    (stage-a-owner-pr-bypass-v1). Any other value is rejected.

.PARAMETER AllowedPath
    One or more repository-relative path globs this dispatch may modify.
    Supports exact paths and trailing '/**' directory globs.

.PARAMETER CanonicalAcTextVersion
    Normalization version for AC text (default: v1).

.PARAMETER ValidateDispatchId
    Dispatch ID to validate.

.PARAMETER ValidateIssueNumber
    Issue number for the dispatch being validated.

.PARAMETER SupersedeDispatchId
    Dispatch ID to supersede (must be currently active).

.PARAMETER SupersedeIssueNumber
    Issue number for the dispatch being superseded.

.PARAMETER SupersedeByDispatchId
    The new dispatch ID that supersedes the old one.

.PARAMETER SupersedeByDriver
    Driver for the new superseding dispatch.

.PARAMETER SupersedeBySpecTaskId
    Spec/task ID for the new superseding dispatch.

.PARAMETER SupersedeByGovernanceVersion
    Governance version for the new superseding dispatch.
    Must equal the current version.

.PARAMETER SupersedeByAllowedPath
    Allowed paths for the new superseding dispatch.

.PARAMETER ExpireDispatchId
    Dispatch ID to expire (must be currently active).

.PARAMETER ExpireIssueNumber
    Issue number for the dispatch being expired.

.PARAMETER ExpirationReason
    Reason for expiration: base_sha_changed, ac_hash_changed, or manual.

.PARAMETER StorePath
    Directory for dispatch files (default: .github/dispatches).

.PARAMETER Owner
    GitHub repository owner (default: Sandape).

.PARAMETER Repo
    GitHub repository name (default: interCraft).

.EXAMPLE
    & dispatch.ps1 -DispatchId 'req-064-feat-20260712-01' -IssueNumber 19 `
        -Driver 'claude-code' -SpecTaskId 'REQ-064' `
        -GovernanceVersion 'stage-a-owner-pr-bypass-v1' `
        -AllowedPath @('scripts/governance/**')

    Creates a new dispatch envelope.

.EXAMPLE
    & dispatch.ps1 -ValidateDispatchId 'req-064-feat-20260712-01' `
        -ValidateIssueNumber 19

    Validates an existing dispatch against current authoritative state.

.EXAMPLE
    & dispatch.ps1 -SupersedeDispatchId 'req-064-feat-20260712-01' `
        -SupersedeIssueNumber 19 `
        -SupersedeByDispatchId 'req-064-feat-20260712-02' `
        -SupersedeByDriver 'codex' -SupersedeBySpecTaskId 'REQ-064' `
        -SupersedeByGovernanceVersion 'stage-a-owner-pr-bypass-v1' `
        -SupersedeByAllowedPath @('scripts/governance/**')

    Marks dispatch v1 as superseded by dispatch v2 with complete new data.

.EXAMPLE
    & dispatch.ps1 -ExpireDispatchId 'req-064-feat-20260712-01' `
        -ExpireIssueNumber 19 -ExpirationReason 'base_sha_changed'

    Marks a dispatch as expired due to base SHA advancement.
#>

[CmdletBinding(DefaultParameterSetName = 'Create')]
param(
    # --- Create parameter set ---
    [Parameter(ParameterSetName = 'Create', Mandatory)]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)+-\d{8}-\d{2,}$')]
    [string] $DispatchId,

    [Parameter(ParameterSetName = 'Create', Mandatory)]
    [ValidateRange(1, [int]::MaxValue)]
    [int] $IssueNumber,

    [Parameter(ParameterSetName = 'Create', Mandatory)]
    [ValidateSet('claude-code', 'codex', 'cursor', 'cursor-automation', 'human')]
    [string] $Driver,

    [Parameter(ParameterSetName = 'Create', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $SpecTaskId,

    [Parameter(ParameterSetName = 'Create', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $GovernanceVersion,

    [Parameter(ParameterSetName = 'Create', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string[]] $AllowedPath,

    [Parameter(ParameterSetName = 'Create')]
    [ValidateSet('v1')]
    [string] $CanonicalAcTextVersion = 'v1',

    # --- Validate parameter set ---
    [Parameter(ParameterSetName = 'Validate', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)+-\d{8}-\d{2,}$')]
    [string] $ValidateDispatchId,

    [Parameter(ParameterSetName = 'Validate', Mandatory)]
    [ValidateRange(1, [int]::MaxValue)]
    [int] $ValidateIssueNumber,

    # --- Supersede parameter set ---
    [Parameter(ParameterSetName = 'Supersede', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)+-\d{8}-\d{2,}$')]
    [string] $SupersedeDispatchId,

    [Parameter(ParameterSetName = 'Supersede', Mandatory)]
    [ValidateRange(1, [int]::MaxValue)]
    [int] $SupersedeIssueNumber,

    [Parameter(ParameterSetName = 'Supersede', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)+-\d{8}-\d{2,}$')]
    [string] $SupersedeByDispatchId,

    [Parameter(ParameterSetName = 'Supersede', Mandatory)]
    [ValidateSet('claude-code', 'codex', 'cursor', 'cursor-automation', 'human')]
    [string] $SupersedeByDriver,

    [Parameter(ParameterSetName = 'Supersede', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $SupersedeBySpecTaskId,

    [Parameter(ParameterSetName = 'Supersede', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $SupersedeByGovernanceVersion,

    [Parameter(ParameterSetName = 'Supersede', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string[]] $SupersedeByAllowedPath,

    # --- Expire parameter set ---
    [Parameter(ParameterSetName = 'Expire', Mandatory)]
    [ValidateNotNullOrEmpty()]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)+-\d{8}-\d{2,}$')]
    [string] $ExpireDispatchId,

    [Parameter(ParameterSetName = 'Expire', Mandatory)]
    [ValidateRange(1, [int]::MaxValue)]
    [int] $ExpireIssueNumber,

    [Parameter(ParameterSetName = 'Expire', Mandatory)]
    [ValidateSet('base_sha_changed', 'ac_hash_changed', 'manual')]
    [string] $ExpirationReason,

    # --- Common ---
    [string] $StorePath = '.github/dispatches',
    [string] $Owner = 'Sandape',
    [string] $Repo = 'interCraft'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ======================================================================
# Constants
# ======================================================================
$CURRENT_GOVERNANCE_VERSION = 'stage-a-owner-pr-bypass-v1'
$VALID_DRIVERS = @('claude-code', 'codex', 'cursor', 'cursor-automation', 'human')
$CONTRACT_FIELDS = @('dispatch_id', 'issue_number', 'driver', 'base_sha', 'spec_task_id',
    'ac_hash', 'canonical_ac_text_version', 'allowed_paths',
    'governance_version', 'created_at', 'state')

# Lock ownership tracking — prevents one process deleting another's lock

# ======================================================================
# Helper functions
# ======================================================================

function Get-DispatchDir {
    param([string] $Path)
    $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    return $resolved
}

function Get-DispatchFilePath {
    param([string] $Dir, [string] $Id)
    if ([string]::IsNullOrWhiteSpace($Id) -or
        $Id -cnotmatch '^[a-z0-9]+(?:-[a-z0-9]+)+-\d{8}-\d{2,}$') {
        throw "DISPATCH_INVALID_ID: dispatch_id '$Id' does not match the canonical lowercase filename-safe format"
    }
    return [System.IO.Path]::Combine($Dir, "$Id.json")
}

function Get-DispatchLockFile {
    param([string] $Dir)
    return [System.IO.Path]::Combine($Dir, '.lock')
}

function Invoke-GhApi {
    <#
    .SYNOPSIS
        Calls gh api and returns the JSON response text.
        Throws on non-zero exit or empty response.
    #>
    param([Parameter(Mandatory)][string[]] $ArgumentList)

    $allOutput = & gh @ArgumentList 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        $errorText = @($allOutput | ForEach-Object { "$_" }) -join "`n"
        throw "DISPATCH_GH_API_FAILED: gh $($ArgumentList -join ' ') failed (exit $exitCode): $errorText"
    }

    $jsonText = @($allOutput | Where-Object { $_ -is [string] }) -join "`n"
    if ([string]::IsNullOrWhiteSpace($jsonText)) {
        throw "DISPATCH_GH_API_FAILED: gh $($ArgumentList -join ' ') returned empty response"
    }

    return $jsonText
}

function ConvertTo-RepositoryPath {
    <#
    .SYNOPSIS
        Validates and normalizes a repository-relative path.
        Rejects absolute, traversal, control-char, .git, and unsupported glob.
    #>
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
        throw "DISPATCH_INVALID_PATH: Path must be repository-relative: '$Path'"
    }

    # Check directory glob syntax
    $isDirGlob = $AllowDirectoryGlob -and $candidate.EndsWith('/**', [StringComparison]::Ordinal)
    $pathPortion = if ($isDirGlob) {
        $candidate.Substring(0, $candidate.Length - 3)
    } else {
        $candidate
    }

    if ($candidate.IndexOfAny([char[]]@('*', '?', '[', ']')) -ge 0 -and -not $isDirGlob) {
        throw "DISPATCH_INVALID_PATH: Only an exact path or a trailing '/**' directory glob is allowed: '$Path'"
    }
    if ($isDirGlob -and $pathPortion.IndexOfAny([char[]]@('*', '?', '[', ']')) -ge 0) {
        throw "DISPATCH_INVALID_PATH: Wildcards not allowed before trailing '/**': '$Path'"
    }

    # Check traversal and .git
    $segments = @($pathPortion.Split('/') | Where-Object { $_ -ne '' })
    $containsTraversal = @($segments | Where-Object { $_ -eq '.' -or $_ -eq '..' }).Count -gt 0
    $targetsGit = @($segments | Where-Object { $_.Equals('.git', [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0
    if ($segments.Count -eq 0 -or $containsTraversal -or $targetsGit) {
        throw "DISPATCH_INVALID_PATH: Path traversal and .git metadata paths are forbidden: '$Path'"
    }

    $normalized = $segments -join '/'
    if ($isDirGlob) {
        return "$normalized/**"
    }
    return $normalized
}

function Test-PathAllowed {
    <#
    .SYNOPSIS
        Checks whether a single path matches any rule in an allowlist.
    #>
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string[]] $Allowed
    )

    foreach ($rule in $Allowed) {
        if ($rule.EndsWith('/**', [StringComparison]::Ordinal)) {
            $prefix = $rule.Substring(0, $rule.Length - 3)
            if ($Path.Equals($prefix, [StringComparison]::Ordinal) -or
                $Path.StartsWith("$prefix/", [StringComparison]::Ordinal)) {
                return $true
            }
        } elseif ($Path.Equals($rule, [StringComparison]::Ordinal)) {
            return $true
        }
    }
    return $false
}

function Get-AuthoritativeMasterSha {
    <#
    .SYNOPSIS
        Fetches authoritative remote master HEAD via gh api.
        Never uses local origin/master.
    #>
    param(
        [Parameter(Mandatory)] [string] $Owner,
        [Parameter(Mandatory)] [string] $Repo
    )

    $rawJson = Invoke-GhApi -ArgumentList @('api', "repos/$Owner/$Repo/git/ref/heads/master")
    $parsed = $rawJson | ConvertFrom-Json
    if (-not $parsed -or -not $parsed.object -or [string]::IsNullOrWhiteSpace($parsed.object.sha)) {
        throw "DISPATCH_GH_API_FAILED: Failed to parse master ref response from gh api"
    }
    $sha = $parsed.object.sha.Trim().ToLowerInvariant()
    if ($sha -notmatch '^[0-9a-f]{40}$') {
        throw "DISPATCH_GH_API_FAILED: Authoritative master response contains invalid SHA '$sha'"
    }
    return $sha
}

function Get-IssueJson {
    <#
    .SYNOPSIS
        Fetches Issue data via gh api and returns parsed JSON object.
    #>
    param(
        [Parameter(Mandatory)] [string] $Owner,
        [Parameter(Mandatory)] [string] $Repo,
        [Parameter(Mandatory)] [int] $IssueNumber
    )

    $rawJson = Invoke-GhApi -ArgumentList @('api', "repos/$Owner/$Repo/issues/$IssueNumber")
    $parsed = $rawJson | ConvertFrom-Json

    if (-not $parsed) {
        throw "DISPATCH_ISSUE_INVALID: Failed to parse Issue #$IssueNumber response from gh api"
    }
    return $parsed
}

function Read-IssueHeadingContent {
    <#
    .SYNOPSIS
        Parses an Issue body for a heading matching the given text (case-insensitive),
        returning the content lines. Accepts any heading level (#, ##, ###, etc.).
        Ends at the next heading of same or higher level.
        Ignores Markdown headings inside fenced code blocks.
    .PARAMETER Body
        Full Issue body string.
    .PARAMETER HeadingText
        The heading text to find (case-insensitive).
    .PARAMETER ErrorPrefix
        Prefix for error codes (e.g. 'AC' or 'PATHS').
    .PARAMETER AllowEmpty
        If true, empty content is allowed (for paths).
    .RETURNS
        Array of content lines (may be empty if AllowEmpty).
    .THROWS
        On missing, duplicate, or (if !AllowEmpty) empty heading.
    #>
    param(
        [Parameter(Mandatory)] [string] $Body,
        [Parameter(Mandatory)] [string] $HeadingText,
        [Parameter(Mandatory)] [string] $ErrorPrefix,
        [switch] $AllowEmpty
    )

    # Normalize line endings
    $normalized = $Body -replace "`r`n", "`n" -replace "`r", "`n"
    $lines = $normalized -split "`n"

    $found = $false
    $duplicate = $false
    $foundLevel = 0
    $contentLines = New-Object 'System.Collections.Generic.List[string]'
    $inContent = $false
    $inCodeFence = $false
    $fenceCharacter = [char]0
    $fenceLength = 0

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        $trimmedLine = $line.Trim()

        # Markdown headings inside fenced code blocks are not headings. Both
        # backtick and tilde fences are recognized, and the closing fence must
        # use the same character with at least the opening length.
        if ($line -match '^[ ]{0,3}(`{3,}|~{3,})') {
            $marker = $matches[1]
            if (-not $inCodeFence) {
                $inCodeFence = $true
                $fenceCharacter = $marker[0]
                $fenceLength = $marker.Length
            }
            elseif ($marker[0] -eq $fenceCharacter -and $marker.Length -ge $fenceLength) {
                $inCodeFence = $false
                $fenceCharacter = [char]0
                $fenceLength = 0
            }
            if ($inContent) {
                $contentLines.Add($line)
            }
            continue
        }

        if ($inCodeFence) {
            # Inside code fence — include in content if collecting
            if ($inContent) {
                $contentLines.Add($line)
            }
            continue
        }

        # Check if this line is a Markdown heading
        if ($line -match '^[ ]{0,3}(#{1,6})[ \t]+(.+?)\s*$') {
            $level = $matches[1].Length
            $text = $matches[2].Trim()
            # ATX closing hash sequences are syntax, not heading text.
            $text = ($text -replace '[ \t]+#+[ \t]*$', '').Trim()

            # Check if this matches our target
            if ($text -eq $HeadingText) {
                if ($found) {
                    $duplicate = $true
                    break
                }
                $found = $true
                $foundLevel = $level
                $inContent = $true
                continue  # skip the heading line itself
            }

            # If we were collecting content and hit a heading of same or higher level,
            # stop collecting but continue scanning for potential duplicate heading
            if ($inContent) {
                if ($level -le $foundLevel) {
                    $inContent = $false
                }
                else {
                    # A deeper heading is part of the selected section and
                    # therefore part of the canonical text.
                    $contentLines.Add($line)
                }
            }
        } elseif ($inContent) {
            $contentLines.Add($line)
        }
    }

    if ($duplicate) {
        throw "${ErrorPrefix}_MALFORMED: Duplicate heading '$HeadingText' found in Issue body"
    }
    if (-not $found) {
        throw "${ErrorPrefix}_MALFORMED: Heading '$HeadingText' not found in Issue body"
    }

    # Remove trailing blank lines
    while ($contentLines.Count -gt 0 -and [string]::IsNullOrWhiteSpace($contentLines[-1])) {
        $contentLines.RemoveAt($contentLines.Count - 1)
    }

    if (-not $AllowEmpty -and $contentLines.Count -eq 0) {
        throw "${ErrorPrefix}_MALFORMED: Heading '$HeadingText' has no content in Issue body"
    }

    return $contentLines.ToArray()
}

function Get-AcHash {
    <#
    .SYNOPSIS
        Computes the canonical v1 AC hash from joined content text.
        The input is the cumulative content string (lines joined with newline).
    #>
    param(
        [Parameter(Mandatory)] [string] $Text,
        [Parameter(Mandatory)] [string] $Version
    )

    if ($Version -ne 'v1') {
        throw "DISPATCH_AC_VERSION_UNSUPPORTED: Unsupported AC text version '$Version'"
    }

    $text = $Text

    # Apply Unicode NFC normalization
    $text = $text.Normalize([System.Text.NormalizationForm]::FormC)

    # Normalize line endings: CRLF/CR → LF
    $text = $text -replace "`r`n", "`n" -replace "`r", "`n"

    # Strip leading/trailing whitespace per line
    $lines = $text -split "`n"
    $trimmed = New-Object 'System.Collections.Generic.List[string]'
    foreach ($line in $lines) {
        $trimmed.Add($line.Trim())
    }

    # Remove trailing blank lines
    while ($trimmed.Count -gt 0 -and $trimmed[-1] -eq '') {
        $trimmed.RemoveAt($trimmed.Count - 1)
    }

    # Check for normalized-empty content
    if ($trimmed.Count -eq 0 -or [string]::IsNullOrWhiteSpace(($trimmed -join ''))) {
        throw 'AC_MALFORMED: Canonical Acceptance Statement content is empty after normalization'
    }

    $normalizedText = $trimmed -join "`n"

    # SHA-256 (UTF-8 no BOM)
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    $bytes = $utf8NoBom.GetBytes($normalizedText)
    $hashBytes = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    $hashHex = [System.BitConverter]::ToString($hashBytes).Replace('-', '').ToLowerInvariant()

    return $hashHex
}

function ConvertFrom-IssuePathLine {
    <#
    .SYNOPSIS
        Parses a single line from the Requested Allowed Paths section.
        Handles raw textarea lines and Markdown bullets with optional backticks.
    .PARAMETER Line
        A single line from the Issue path section.
    .RETURNS
        The extracted path string, or $null if the line is blank/empty.
    #>
    param([Parameter(Mandatory)] [AllowEmptyString()] [string] $Line)

    $candidate = $Line.Trim()
    if ([string]::IsNullOrWhiteSpace($candidate)) { return $null }

    # Strip Markdown bullet prefix ("- " or "* ")
    if ($candidate -match '^[-*]\s+(.*)$') {
        $candidate = $matches[1].Trim()
    }

    # Strip surrounding backticks (e.g. - `scripts/**`)
    if ($candidate -match '^``(.+)``$' -or $candidate -match '^`(.+)`$') {
        $candidate = $matches[1].Trim()
    }

    if ([string]::IsNullOrWhiteSpace($candidate)) { return $null }
    return $candidate
}

function Assert-ValidDispatchEnvelope {
    <#
    .SYNOPSIS
        Validates a parsed dispatch envelope against the contract.
        Throws DISPATCH_CORRUPT_STORE on any violation.
    .PARAMETER Dispatch
        Parsed dispatch object (from ConvertFrom-Json).
    .PARAMETER ExpectedFileName
        Expected filename (without .json) for ID/filename consistency check.
        Omit when the filename is unknown (e.g., during inline validation).
    #>
    param(
        [Parameter(Mandatory)] [PSCustomObject] $Dispatch,
        [string] $ExpectedFileName
    )

    # Check for unexpected fields (contract fields only)
    $properties = @($Dispatch.PSObject.Properties | ForEach-Object { $_.Name })
    foreach ($prop in $properties) {
        if ($prop -notin $CONTRACT_FIELDS) {
            throw "DISPATCH_CORRUPT_STORE: Dispatch file has unexpected field '$prop'. Only contract fields are permitted."
        }
    }

    # Check all required fields are present and non-null
    $required = @('dispatch_id', 'issue_number', 'driver', 'base_sha', 'spec_task_id',
        'ac_hash', 'canonical_ac_text_version', 'allowed_paths',
        'governance_version', 'created_at', 'state')
    foreach ($field in $required) {
        $val = $Dispatch.$field
        if ($null -eq $val) {
            throw "DISPATCH_CORRUPT_STORE: Missing required field '$field'"
        }
    }

    # dispatch_id must follow the durable contract format.
    if ("$($Dispatch.dispatch_id)" -cnotmatch '^[a-z0-9]+(-[a-z0-9]+)+-\d{8}-\d{2,}$') {
        throw "DISPATCH_CORRUPT_STORE: dispatch_id '$($Dispatch.dispatch_id)' does not match the required format"
    }

    # Filename consistency
    if ($ExpectedFileName -and $Dispatch.dispatch_id -cne $ExpectedFileName) {
        throw "DISPATCH_CORRUPT_STORE: dispatch_id '$($Dispatch.dispatch_id)' does not match filename '$ExpectedFileName'"
    }

    # issue_number must be positive
    if (-not ($Dispatch.issue_number -is [int] -or $Dispatch.issue_number -is [long])) {
        throw "DISPATCH_CORRUPT_STORE: issue_number must be a JSON integer"
    }
    $issueNum = [int]$Dispatch.issue_number
    if ($issueNum -le 0) {
        throw "DISPATCH_CORRUPT_STORE: issue_number '$issueNum' must be positive"
    }

    if ([string]::IsNullOrWhiteSpace("$($Dispatch.spec_task_id)")) {
        throw 'DISPATCH_CORRUPT_STORE: spec_task_id is empty or whitespace'
    }

    # base_sha must be 40-character lowercase hex
    $baseSha = "$($Dispatch.base_sha)"
    if ($baseSha -cnotmatch '^[0-9a-f]{40}$') {
        throw "DISPATCH_CORRUPT_STORE: base_sha '$($Dispatch.base_sha)' is not a valid 40-character hex string"
    }

    # ac_hash must be 64-character lowercase hex, or $null for normalized-empty
    $acHash = "$($Dispatch.ac_hash)"
    if ($acHash -cnotmatch '^[0-9a-f]{64}$') {
        throw "DISPATCH_CORRUPT_STORE: ac_hash '$($Dispatch.ac_hash)' is not a valid 64-character hex string"
    }

    # canonical_ac_text_version must be 'v1'
    if ("$($Dispatch.canonical_ac_text_version)" -cne 'v1') {
        throw "DISPATCH_CORRUPT_STORE: canonical_ac_text_version '$($Dispatch.canonical_ac_text_version)' must be 'v1'"
    }

    # governance_version must match current version
    if ("$($Dispatch.governance_version)" -cne $CURRENT_GOVERNANCE_VERSION) {
        throw "DISPATCH_CORRUPT_STORE: governance_version '$($Dispatch.governance_version)' does not match current version '$CURRENT_GOVERNANCE_VERSION'"
    }

    # driver must be valid
    if ($VALID_DRIVERS -cnotcontains "$($Dispatch.driver)") {
        throw "DISPATCH_CORRUPT_STORE: driver '$($Dispatch.driver)' is not valid"
    }

    # state must be valid
    if (@('active', 'superseded', 'expired') -cnotcontains "$($Dispatch.state)") {
        throw "DISPATCH_CORRUPT_STORE: state '$($Dispatch.state)' is not valid"
    }

    # allowed_paths must be non-empty array
    if ($Dispatch.allowed_paths -is [string] -or -not ($Dispatch.allowed_paths -is [System.Collections.IEnumerable])) {
        throw 'DISPATCH_CORRUPT_STORE: allowed_paths must be a JSON array'
    }
    $paths = @($Dispatch.allowed_paths)
    if ($paths.Count -eq 0) {
        throw "DISPATCH_CORRUPT_STORE: allowed_paths is empty"
    }
    # Each path must be validatable
    $normalizedPaths = New-Object 'System.Collections.Generic.List[string]'
    foreach ($p in $paths) {
        if ([string]::IsNullOrWhiteSpace($p)) {
            throw "DISPATCH_CORRUPT_STORE: allowed_paths contains empty or whitespace entry"
        }
        try {
            $normalizedPaths.Add((ConvertTo-RepositoryPath -Path $p -AllowDirectoryGlob))
        } catch {
            throw "DISPATCH_CORRUPT_STORE: allowed_path '$p' is invalid: $_"
        }
    }
    $uniquePaths = @($normalizedPaths | Sort-Object -CaseSensitive -Unique)
    if ($uniquePaths.Count -ne $normalizedPaths.Count) {
        throw 'DISPATCH_CORRUPT_STORE: allowed_paths contains duplicate entries'
    }

    # created_at must be parseable as ISO 8601 UTC
    $createdStr = "$($Dispatch.created_at)"
    try {
        $null = [System.DateTime]::ParseExact($createdStr, 'yyyy-MM-ddTHH:mm:ssZ',
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::AssumeUniversal)
    } catch {
        throw "DISPATCH_CORRUPT_STORE: created_at '$createdStr' is not a valid ISO 8601 UTC datetime (yyyy-MM-ddTHH:mm:ssZ)"
    }
}

function Read-DispatchFile {
    <#
    .SYNOPSIS
        Reads and parses a dispatch JSON file, then validates the envelope.
    #>
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [switch] $SkipValidation
    )

    if (-not [System.IO.File]::Exists($FilePath)) {
        throw "DISPATCH_NOT_FOUND: Dispatch file not found: $FilePath"
    }

    $raw = [System.IO.File]::ReadAllText($FilePath, [System.Text.Encoding]::UTF8)
    try {
        $parsed = $raw | ConvertFrom-Json
    }
    catch {
        throw "DISPATCH_CORRUPT_STORE: Invalid JSON in '$FilePath': $($_.Exception.Message)"
    }

    if (-not $parsed) {
        throw "DISPATCH_INVALID_FILE: Failed to parse dispatch file: $FilePath"
    }

    if (-not $SkipValidation) {
        $filename = [System.IO.Path]::GetFileNameWithoutExtension($FilePath)
        Assert-ValidDispatchEnvelope -Dispatch $parsed -ExpectedFileName $filename
    }

    return $parsed
}

function Get-ActiveDispatchesForIssue {
    <#
    .SYNOPSIS
        Scans the dispatch directory for any active dispatch matching the given Issue.
        Validates every *.json file; throws DISPATCH_CORRUPT_STORE on invalid files.
        Never silently skips malformed files.
    #>
    param(
        [Parameter(Mandatory)] [string] $Dir,
        [Parameter(Mandatory)] [int] $IssueNumber,
        [switch] $IncludeTerminal
    )

    if (-not (Test-Path -LiteralPath $Dir)) {
        return @()
    }

    $results = @()
    $jsonFiles = @([System.IO.Directory]::GetFiles($Dir) | Where-Object {
        [System.IO.Path]::GetExtension($_).Equals('.json', [StringComparison]::OrdinalIgnoreCase)
    })
    foreach ($file in $jsonFiles) {
        # Read-DispatchFile validates and throws on corruption
        $dispatch = Read-DispatchFile -FilePath $file

        if ($dispatch.issue_number -eq $IssueNumber) {
            if ($IncludeTerminal -or $dispatch.state -eq 'active') {
                $results += [PSCustomObject]@{
                    DispatchId = $dispatch.dispatch_id
                    State = $dispatch.state
                    FilePath = $file
                    Dispatch = $dispatch
                }
            }
        }
    }
    return $results
}

function Assert-NoDispatchRecoveryArtifacts {
    <#
    .SYNOPSIS
        Fails closed when a prior hard crash may have left ambiguous state.
        Recovery artifacts are never deleted automatically.
    #>
    param(
        [Parameter(Mandatory)] [string] $Dir,
        [switch] $IgnoreOwnedLock
    )

    if (-not [System.IO.Directory]::Exists($Dir)) {
        return
    }

    $artifacts = New-Object 'System.Collections.Generic.List[string]'
    foreach ($file in [System.IO.Directory]::GetFiles($Dir)) {
        $name = [System.IO.Path]::GetFileName($file)
        if (($name -eq '.lock' -and -not $IgnoreOwnedLock) -or
            $name.EndsWith('.tmp', [StringComparison]::OrdinalIgnoreCase) -or
            $name.EndsWith('.bak', [StringComparison]::OrdinalIgnoreCase)) {
            $artifacts.Add($name)
        }
    }

    if ($artifacts.Count -gt 0) {
        throw "DISPATCH_RECOVERY_REQUIRED: Ambiguous dispatch recovery artifacts exist: $(@($artifacts | Sort-Object) -join ', '). Confirm no writer is active and inspect the files before an explicit manual recovery; nothing was deleted automatically."
    }
}

function Invoke-WithDispatchLock {
    <#
    .SYNOPSIS
        Acquires an exclusive file lock on the dispatch directory,
        runs the script block, then releases the lock.
        Tracks lock ownership — only a process that acquired the lock deletes it.
    #>
    param(
        [Parameter(Mandatory)] [scriptblock] $ScriptBlock,
        [Parameter(Mandatory)] [string] $Dir,
        [int] $MaxRetries = 10,
        [int] $RetryDelayMs = 200
    )

    $lockFile = Get-DispatchLockFile -Dir $Dir
    $lockStream = $null
    $owned = $false

    try {
        # Ensure directory exists
        if (-not (Test-Path -LiteralPath $Dir)) {
            New-Item -ItemType Directory -Path $Dir -Force | Out-Null
        }

        # Acquire lock
        for ($attempt = 0; $attempt -lt $MaxRetries; $attempt++) {
            try {
                $lockStream = [System.IO.File]::Open(
                    $lockFile,
                    [System.IO.FileMode]::CreateNew,
                    [System.IO.FileAccess]::Write,
                    [System.IO.FileShare]::None
                )
                $owned = $true
                break
            } catch [System.IO.IOException] {
                if ($attempt -eq $MaxRetries - 1) {
                    throw "DISPATCH_LOCK_FAILED: Could not acquire dispatch lock after $MaxRetries attempts. A stale lock may exist at: $lockFile. Remove it manually after confirming no other writer is active."
                }
                Start-Sleep -Milliseconds $RetryDelayMs
            }
        }

        Assert-NoDispatchRecoveryArtifacts -Dir $Dir -IgnoreOwnedLock

        # Execute the protected operation
        return & $ScriptBlock
    }
    finally {
        if ($lockStream -ne $null) {
            $lockStream.Close()
            $lockStream.Dispose()
        }
        # Only delete the lock if THIS process acquired it
        if ($owned) {
            if ([System.IO.File]::Exists($lockFile)) {
                [System.IO.File]::Delete($lockFile)
            }
        }
    }
}

function Invoke-AtomicWriteForNew {
    <#
    .SYNOPSIS
        Writes content to a NEW file atomically using same-volume temp + Move.
        Temp name is collision-free (GUID). Cleans up on failure.
        A hard crash may leave the owned .tmp file. Later operations fail
        closed until an operator inspects and explicitly recovers it.
    #>
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Content
    )

    $guid = [guid]::NewGuid().ToString('N')
    $tmpPath = "$Path.$guid.tmp"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false

    try {
        [System.IO.File]::WriteAllText($tmpPath, $Content, $utf8NoBom)
        [System.IO.File]::Move($tmpPath, $Path)
    } catch {
        if ([System.IO.File]::Exists($tmpPath)) {
            [System.IO.File]::Delete($tmpPath)
        }
        throw
    }
}

function Invoke-AtomicWriteForReplace {
    <#
    .SYNOPSIS
        Replaces an existing file atomically using File.Replace with backup.
        Temp and backup names are collision-free (GUID).
        Cleans up temp and backup files on caught failures.
        A hard crash may leave .tmp or .bak. Later operations fail closed;
        ambiguous recovery artifacts are never deleted automatically.
    #>
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $Content
    )

    $guid = [guid]::NewGuid().ToString('N')
    $tmpPath = "$Path.$guid.tmp"
    $bakPath = "$Path.$guid.bak"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false

    try {
        [System.IO.File]::WriteAllText($tmpPath, $Content, $utf8NoBom)
        [System.IO.File]::Replace($tmpPath, $Path, $bakPath)
        # Clean up backup on success
        if ([System.IO.File]::Exists($bakPath)) {
            [System.IO.File]::Delete($bakPath)
        }
    } catch {
        if ([System.IO.File]::Exists($tmpPath)) {
            [System.IO.File]::Delete($tmpPath)
        }
        # Preserve a backup left by a failed/ambiguous File.Replace call.
        # The next operation detects it and requires explicit recovery.
        throw
    }
}

function ConvertTo-DispatchJson {
    <#
    .SYNOPSIS
        Serializes a dispatch envelope hashtable to pretty-printed JSON.
    #>
    param([Parameter(Mandatory)] [hashtable] $Envelope)

    return $Envelope | ConvertTo-Json -Depth 5
}

function New-DispatchEnvelope {
    <#
    .SYNOPSIS
        Creates a new dispatch envelope and writes it atomically.
        Uses Invoke-AtomicWriteForNew for NEW file creation.
    #>
    param(
        [Parameter(Mandatory)] [string] $DispatchId,
        [Parameter(Mandatory)] [int] $IssueNumber,
        [Parameter(Mandatory)] [string] $Driver,
        [Parameter(Mandatory)] [string] $SpecTaskId,
        [Parameter(Mandatory)] [string] $GovernanceVersion,
        [Parameter(Mandatory)] [string[]] $AllowedPaths,
        [Parameter(Mandatory)] [string] $BaseSha,
        [Parameter(Mandatory)] [string] $AcHash,
        [Parameter(Mandatory)] [string] $CanonicalAcTextVersion,
        [Parameter(Mandatory)] [string] $Dir
    )

    $envelope = @{
        dispatch_id = $DispatchId
        issue_number = $IssueNumber
        driver = $Driver
        base_sha = $BaseSha
        spec_task_id = $SpecTaskId
        ac_hash = $AcHash
        canonical_ac_text_version = $CanonicalAcTextVersion
        allowed_paths = @($AllowedPaths | Sort-Object -Unique)
        governance_version = $GovernanceVersion
        created_at = [System.DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
        state = 'active'
    }

    $json = ConvertTo-DispatchJson -Envelope $envelope
    $filePath = Get-DispatchFilePath -Dir $Dir -Id $DispatchId
    Invoke-AtomicWriteForNew -Path $filePath -Content $json

    return [PSCustomObject]@{
        ok = $true
        operation = 'create'
        dispatch_id = $DispatchId
        issue_number = $IssueNumber
        state = 'active'
        file = $filePath
    }
}

function Update-DispatchState {
    <#
    .SYNOPSIS
        Updates a dispatch file with a new state.
        Only sets contract fields (no lifecycle metadata — Git history records transitions).
        Must be called while holding the dispatch lock.
        Uses Invoke-AtomicWriteForReplace for atomic replacement.
    #>
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [Parameter(Mandatory)] [string] $NewState
    )

    $dispatch = Read-DispatchFile -FilePath $FilePath
    $envelope = @{
        dispatch_id = $dispatch.dispatch_id
        issue_number = $dispatch.issue_number
        driver = $dispatch.driver
        base_sha = $dispatch.base_sha
        spec_task_id = $dispatch.spec_task_id
        ac_hash = $dispatch.ac_hash
        canonical_ac_text_version = $dispatch.canonical_ac_text_version
        allowed_paths = @($dispatch.allowed_paths)
        governance_version = $dispatch.governance_version
        created_at = $dispatch.created_at
        state = $NewState
    }

    $json = ConvertTo-DispatchJson -Envelope $envelope
    Invoke-AtomicWriteForReplace -Path $FilePath -Content $json

    return [PSCustomObject]@{
        ok = $true
        operation = 'state-update'
        dispatch_id = $dispatch.dispatch_id
        state = $NewState
        file = $FilePath
    }
}

# ======================================================================
# Operation: Create
# ======================================================================
function Invoke-Create {
    Write-Verbose "DISPATCH: Creating dispatch '$DispatchId' for Issue #$IssueNumber"

    # --- Validate governance version ---
    if ($GovernanceVersion -cne $CURRENT_GOVERNANCE_VERSION) {
        throw "DISPATCH_INVALID_GOVERNANCE_VERSION: Governance version '$GovernanceVersion' does not match current version '$CURRENT_GOVERNANCE_VERSION'"
    }

    # --- Validate dispatch_id format constraint from contract ---
    if ($DispatchId -cnotmatch '^[a-z0-9]+(-[a-z0-9]+)+-\d{8}-\d{2,}$') {
        throw "DISPATCH_INVALID_ID: dispatch_id '$DispatchId' does not match required format <req-prefix>-<purpose>-<yyyymmdd>-<nn>"
    }

    # --- Validate driver ---
    $driverMatch = $false
    foreach ($valid in $VALID_DRIVERS) {
        if ($Driver -eq $valid) { $driverMatch = $true; break }
    }
    if (-not $driverMatch) {
        throw "DISPATCH_INVALID_DRIVER: Driver '$Driver' is not valid. Must be one of: $($VALID_DRIVERS -join ', ')"
    }

    # --- Resolve paths ---
    $dir = Get-DispatchDir -Path $StorePath
    $dispatchFile = Get-DispatchFilePath -Dir $dir -Id $DispatchId

    # --- Check dispatch_id uniqueness (file must not exist) ---
    if ([System.IO.File]::Exists($dispatchFile)) {
        throw "DISPATCH_DUPLICATE_ID: Dispatch ID '$DispatchId' already exists at: $dispatchFile"
    }

    # --- Fetch authoritative master SHA ---
    Write-Verbose "DISPATCH: Fetching authoritative master SHA from gh api..."
    $baseSha = Get-AuthoritativeMasterSha -Owner $Owner -Repo $Repo

    # --- Fetch Issue data ---
    Write-Verbose "DISPATCH: Fetching Issue #$IssueNumber from gh api..."
    $issue = Get-IssueJson -Owner $Owner -Repo $Repo -IssueNumber $IssueNumber

    # --- Check Issue is open ---
    if ($issue.state -ne 'open') {
        throw "DISPATCH_ISSUE_CLOSED: Issue #$IssueNumber is not open (state='$($issue.state)')"
    }

    # --- Parse Canonical Acceptance Statement from Issue body ---
    $issueBody = if ([string]::IsNullOrWhiteSpace($issue.body)) { '' } else { $issue.body }
    $acLines = @(Read-IssueHeadingContent -Body $issueBody -HeadingText 'Canonical Acceptance Statement' -ErrorPrefix 'AC' -AllowEmpty:$false)

    # --- Compute AC hash ---
    $acText = $acLines -join "`n"

    # Check for normalized-empty AC content (all whitespace lines)
    $nonEmptyLines = @($acLines | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
    if ($nonEmptyLines.Count -eq 0) {
        throw "AC_MALFORMED: Canonical Acceptance Statement content is empty after normalization"
    }

    $acHash = Get-AcHash -Text $acText -Version $CanonicalAcTextVersion
    if ($null -eq $acHash) {
        throw "AC_MALFORMED: Canonical Acceptance Statement content is empty after normalization"
    }

    # --- Parse Requested Allowed Paths from Issue body (mandatory) ---
    $issuePathLines = @(Read-IssueHeadingContent -Body $issueBody -HeadingText 'Requested Allowed Paths' -ErrorPrefix 'PATHS' -AllowEmpty:$false)

    # --- Validate and normalize Issue requested paths ---
    $issuePaths = @()
    foreach ($line in $issuePathLines) {
        $candidate = ConvertFrom-IssuePathLine -Line $line
        if ($null -eq $candidate) { continue }
        try {
            $normalized = ConvertTo-RepositoryPath -Path $candidate -AllowDirectoryGlob
            $issuePaths += $normalized
        } catch {
            throw "DISPATCH_ISSUE_INVALID_PATH: Issue requested allowed path '$candidate' is invalid: $_"
        }
    }
    if ($issuePaths.Count -eq 0) {
        throw "PATHS_MALFORMED: Requested Allowed Paths section has no valid paths in Issue body"
    }
    $issuePaths = @($issuePaths | Sort-Object -Unique)

    # --- Validate and normalize caller-supplied AllowedPath ---
    $normalizedAllowed = @()
    foreach ($path in $AllowedPath) {
        $normalized = ConvertTo-RepositoryPath -Path $path -AllowDirectoryGlob
        $normalizedAllowed += $normalized
    }
    $normalizedAllowed = @($normalizedAllowed | Sort-Object -Unique)

    # --- Check each dispatch path is within Issue's requested paths ---
    foreach ($dpath in $normalizedAllowed) {
        if (-not (Test-PathAllowed -Path $dpath -Allowed $issuePaths)) {
            throw "DISPATCH_PATH_ESCAPE: Dispatch path '$dpath' is not within Issue #$IssueNumber requested allowed paths: $($issuePaths -join ', ')"
        }
    }

    # --- Acquire lock, check for existing active dispatch, and write ---
    # Ensure directory exists
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $result = Invoke-WithDispatchLock -Dir $dir -ScriptBlock {
        $lockedMasterSha = Get-AuthoritativeMasterSha -Owner $Owner -Repo $Repo
        if ($lockedMasterSha -ne $baseSha) {
            throw "DISPATCH_REMOTE_CHANGED_RETRY: master advanced from '$baseSha' to '$lockedMasterSha' while preparing Create"
        }
        $lockedIssue = Get-IssueJson -Owner $Owner -Repo $Repo -IssueNumber $IssueNumber
        if ($lockedIssue.state -ne 'open' -or "$($lockedIssue.body)" -cne "$($issue.body)") {
            throw "DISPATCH_REMOTE_CHANGED_RETRY: Issue #$IssueNumber changed while preparing Create"
        }

        # Check for existing active dispatch for this Issue (under lock)
        # Create MUST reject if any active dispatch exists — never auto-supersede
        $activeForIssue = @(Get-ActiveDispatchesForIssue -Dir $dir -IssueNumber $IssueNumber)

        if ($activeForIssue.Count -gt 0) {
            $existing = $activeForIssue[0]
            throw "DISPATCH_ACTIVE_EXISTS: An active dispatch '$($existing.DispatchId)' (driver=$($existing.Dispatch.driver)) already exists for Issue #$IssueNumber. Create rejected. Use explicit Supersede to replace it, or create a new dispatch for a different Issue."
        }

        # Create new dispatch
        return New-DispatchEnvelope -DispatchId $DispatchId -IssueNumber $IssueNumber -Driver $Driver `
            -SpecTaskId $SpecTaskId -GovernanceVersion $GovernanceVersion `
            -AllowedPaths $normalizedAllowed -BaseSha $baseSha -AcHash $acHash `
            -CanonicalAcTextVersion $CanonicalAcTextVersion -Dir $dir
    }

    return $result
}

# ======================================================================
# Operation: Validate
# ======================================================================
function Invoke-Validate {
    Write-Verbose "DISPATCH: Validating dispatch '$ValidateDispatchId' for Issue #$ValidateIssueNumber"

    $dir = Get-DispatchDir -Path $StorePath
    $dispatchFile = Get-DispatchFilePath -Dir $dir -Id $ValidateDispatchId

    # Validation is read-only and does not acquire the mutation lock. Any
    # lock/temp/backup artifact makes the store ambiguous and fails closed.
    Assert-NoDispatchRecoveryArtifacts -Dir $dir

    # --- Read dispatch file (validates envelope) ---
    $dispatch = Read-DispatchFile -FilePath $dispatchFile

    # --- Check dispatch_id consistency ---
    if ($dispatch.dispatch_id -ne $ValidateDispatchId) {
        throw "DISPATCH_INVALID_FILE: File dispatch_id '$($dispatch.dispatch_id)' does not match expected '$ValidateDispatchId'"
    }

    # --- Check issue_number consistency ---
    if ($dispatch.issue_number -ne $ValidateIssueNumber) {
        throw "DISPATCH_ISSUE_MISMATCH: Dispatch issue_number $($dispatch.issue_number) does not match expected $ValidateIssueNumber"
    }

    # --- Check governance_version matches current ---
    if ($dispatch.governance_version -ne $CURRENT_GOVERNANCE_VERSION) {
        throw "DISPATCH_INVALID_GOVERNANCE_VERSION: Dispatch governance_version '$($dispatch.governance_version)' does not match current version '$CURRENT_GOVERNANCE_VERSION'"
    }

    # --- Check state is active (reject terminal) ---
    if ($dispatch.state -ne 'active') {
        throw "DISPATCH_INACTIVE: Dispatch '$ValidateDispatchId' is in terminal state '$($dispatch.state)' and cannot be validated as active"
    }

    # --- Fetch authoritative master SHA ---
    Write-Verbose "DISPATCH: Fetching authoritative master SHA..."
    $currentMasterSha = Get-AuthoritativeMasterSha -Owner $Owner -Repo $Repo

    # --- Check base_sha is still current ---
    $expectedBase = $dispatch.base_sha.ToLowerInvariant()
    if ($currentMasterSha -ne $expectedBase) {
        throw "DISPATCH_BASE_STALE: Dispatch base_sha '$expectedBase' no longer equals authoritative master '$currentMasterSha'"
    }

    # --- Fetch Issue data ---
    Write-Verbose "DISPATCH: Fetching Issue #$ValidateIssueNumber..."
    $issue = Get-IssueJson -Owner $Owner -Repo $Repo -IssueNumber $ValidateIssueNumber

    # --- Check Issue is open ---
    if ($issue.state -ne 'open') {
        throw "DISPATCH_ISSUE_CLOSED: Issue #$ValidateIssueNumber is not open (state='$($issue.state)')"
    }

    # --- Parse Canonical Acceptance Statement and re-compute hash ---
    $issueBody = if ([string]::IsNullOrWhiteSpace($issue.body)) { '' } else { $issue.body }
    $acLines = @(Read-IssueHeadingContent -Body $issueBody -HeadingText 'Canonical Acceptance Statement' -ErrorPrefix 'AC' -AllowEmpty:$false)
    $currentAcText = $acLines -join "`n"
    $currentAcHash = Get-AcHash -Text $currentAcText -Version $dispatch.canonical_ac_text_version

    if ($null -eq $currentAcHash) {
        throw "DISPATCH_AC_HASH_MISMATCH: AC hash cannot be computed — current AC content is empty after normalization"
    }

    if ($currentAcHash -ne $dispatch.ac_hash) {
        throw "DISPATCH_AC_HASH_MISMATCH: AC hash changed. Expected '$($dispatch.ac_hash)', current '$currentAcHash'"
    }

    # --- Parse Issue allowed paths (mandatory) ---
    $issuePathLines = @(Read-IssueHeadingContent -Body $issueBody -HeadingText 'Requested Allowed Paths' -ErrorPrefix 'PATHS' -AllowEmpty:$false)

    $issuePaths = @()
    foreach ($line in $issuePathLines) {
        $candidate = ConvertFrom-IssuePathLine -Line $line
        if ($null -eq $candidate) { continue }
        try {
            $normalized = ConvertTo-RepositoryPath -Path $candidate -AllowDirectoryGlob
            $issuePaths += $normalized
        } catch {
            throw "DISPATCH_ISSUE_INVALID_PATH: Issue requested allowed path '$candidate' is invalid: $_"
        }
    }
    if ($issuePaths.Count -eq 0) {
        throw "DISPATCH_PATH_ESCAPE: Issue #$ValidateIssueNumber has no valid allowed paths — dispatch cannot be scoped"
    }
    $issuePaths = @($issuePaths | Sort-Object -Unique)

    # --- Check dispatch paths are within Issue's paths ---
    foreach ($dpath in @($dispatch.allowed_paths)) {
        if (-not (Test-PathAllowed -Path $dpath -Allowed $issuePaths)) {
            throw "DISPATCH_PATH_ESCAPE: Dispatch allowed path '$dpath' is no longer within Issue #$ValidateIssueNumber requested allowed paths: $($issuePaths -join ', ')"
        }
    }

    # --- Check no duplicate active dispatch for same Issue ---
    $activeForIssue = Get-ActiveDispatchesForIssue -Dir $dir -IssueNumber $ValidateIssueNumber
    foreach ($existing in $activeForIssue) {
        if ($existing.DispatchId -ne $ValidateDispatchId) {
            throw "DISPATCH_DUPLICATE_ACTIVE: Another active dispatch '$($existing.DispatchId)' exists for Issue #$ValidateIssueNumber"
        }
    }

    return [PSCustomObject]@{
        ok = $true
        operation = 'validate'
        dispatch_id = $ValidateDispatchId
        issue_number = $ValidateIssueNumber
        state = $dispatch.state
        base_sha = $dispatch.base_sha
        ac_hash = $dispatch.ac_hash
        status = 'valid'
    }
}

# ======================================================================
# Operation: Supersede
# ======================================================================
function Invoke-Supersede {
    Write-Verbose "DISPATCH: Superseding dispatch '$SupersedeDispatchId' by '$SupersedeByDispatchId'"

    # --- Validate governance version for new dispatch ---
    if ($SupersedeByGovernanceVersion -cne $CURRENT_GOVERNANCE_VERSION) {
        throw "DISPATCH_INVALID_GOVERNANCE_VERSION: Superseding governance version '$SupersedeByGovernanceVersion' does not match current version '$CURRENT_GOVERNANCE_VERSION'"
    }

    # --- Validate new dispatch_id format ---
    if ($SupersedeByDispatchId -cnotmatch '^[a-z0-9]+(-[a-z0-9]+)+-\d{8}-\d{2,}$') {
        throw "DISPATCH_INVALID_ID: Superseding dispatch_id '$SupersedeByDispatchId' does not match required format <req-prefix>-<purpose>-<yyyymmdd>-<nn>"
    }

    $dir = Get-DispatchDir -Path $StorePath
    $oldFile = Get-DispatchFilePath -Dir $dir -Id $SupersedeDispatchId
    $newFile = Get-DispatchFilePath -Dir $dir -Id $SupersedeByDispatchId

    # --- Check new dispatch_id doesn't already exist ---
    if ([System.IO.File]::Exists($newFile)) {
        throw "DISPATCH_DUPLICATE_ID: New dispatch ID '$SupersedeByDispatchId' already exists at: $newFile"
    }

    # --- Fetch authoritative master SHA ---
    Write-Verbose "DISPATCH: Fetching authoritative master SHA..."
    $baseSha = Get-AuthoritativeMasterSha -Owner $Owner -Repo $Repo

    # --- Fetch Issue data ---
    Write-Verbose "DISPATCH: Fetching Issue #$SupersedeIssueNumber..."
    $issue = Get-IssueJson -Owner $Owner -Repo $Repo -IssueNumber $SupersedeIssueNumber

    if ($issue.state -ne 'open') {
        throw "DISPATCH_ISSUE_CLOSED: Issue #$SupersedeIssueNumber is not open (state='$($issue.state)')"
    }

    # --- Parse AC and compute hash from fresh Issue ---
    $issueBody = if ([string]::IsNullOrWhiteSpace($issue.body)) { '' } else { $issue.body }
    $acLines = @(Read-IssueHeadingContent -Body $issueBody -HeadingText 'Canonical Acceptance Statement' -ErrorPrefix 'AC' -AllowEmpty:$false)
    $acText = $acLines -join "`n"

    $nonEmptyLines = @($acLines | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
    if ($nonEmptyLines.Count -eq 0) {
        throw "AC_MALFORMED: Canonical Acceptance Statement content is empty after normalization"
    }

    $acHash = Get-AcHash -Text $acText -Version 'v1'
    if ($null -eq $acHash) {
        throw "AC_MALFORMED: Canonical Acceptance Statement content is empty after normalization"
    }

    # --- Parse Issue paths (mandatory) ---
    $issuePathLines = @(Read-IssueHeadingContent -Body $issueBody -HeadingText 'Requested Allowed Paths' -ErrorPrefix 'PATHS' -AllowEmpty:$false)

    $issuePaths = @()
    foreach ($line in $issuePathLines) {
        $candidate = ConvertFrom-IssuePathLine -Line $line
        if ($null -eq $candidate) { continue }
        try {
            $normalized = ConvertTo-RepositoryPath -Path $candidate -AllowDirectoryGlob
            $issuePaths += $normalized
        } catch {
            throw "DISPATCH_ISSUE_INVALID_PATH: Issue requested allowed path '$candidate' is invalid: $_"
        }
    }
    if ($issuePaths.Count -eq 0) {
        throw "PATHS_MALFORMED: Requested Allowed Paths section has no valid paths in Issue body"
    }
    $issuePaths = @($issuePaths | Sort-Object -Unique)

    # --- Validate and normalize superseding dispatch paths ---
    $normalizedAllowed = @()
    foreach ($path in $SupersedeByAllowedPath) {
        $normalized = ConvertTo-RepositoryPath -Path $path -AllowDirectoryGlob
        $normalizedAllowed += $normalized
    }
    $normalizedAllowed = @($normalizedAllowed | Sort-Object -Unique)

    # --- Check each superseding dispatch path is within Issue's paths ---
    foreach ($dpath in $normalizedAllowed) {
        if (-not (Test-PathAllowed -Path $dpath -Allowed $issuePaths)) {
            throw "DISPATCH_PATH_ESCAPE: Superseding dispatch path '$dpath' is not within Issue #$SupersedeIssueNumber requested allowed paths: $($issuePaths -join ', ')"
        }
    }

    # --- Ensure directory exists ---
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    # --- Acquire lock and execute conservative crash order ---
    $result = Invoke-WithDispatchLock -Dir $dir -ScriptBlock {
        # Re-fetch both remote authorities while holding the mutation lock so
        # the values used for the write cannot silently drift after pre-checks.
        $lockedMasterSha = Get-AuthoritativeMasterSha -Owner $Owner -Repo $Repo
        if ($lockedMasterSha -ne $baseSha) {
            throw "DISPATCH_REMOTE_CHANGED_RETRY: master advanced from '$baseSha' to '$lockedMasterSha' while preparing Supersede"
        }
        $lockedIssue = Get-IssueJson -Owner $Owner -Repo $Repo -IssueNumber $SupersedeIssueNumber
        if ($lockedIssue.state -ne 'open' -or "$($lockedIssue.body)" -cne "$($issue.body)") {
            throw "DISPATCH_REMOTE_CHANGED_RETRY: Issue #$SupersedeIssueNumber changed while preparing Supersede"
        }

        # Re-read old dispatch under lock (TOCTOU safety)
        $oldDispatch = Read-DispatchFile -FilePath $oldFile

        if ([int]$oldDispatch.issue_number -ne $SupersedeIssueNumber) {
            throw "DISPATCH_ISSUE_MISMATCH: Dispatch issue_number $($oldDispatch.issue_number) does not match expected $SupersedeIssueNumber"
        }
        if ($oldDispatch.state -ne 'active') {
            throw "DISPATCH_INACTIVE: Dispatch '$SupersedeDispatchId' is in state '$($oldDispatch.state)' and cannot be superseded"
        }
        if ([System.IO.File]::Exists($newFile)) {
            throw "DISPATCH_DUPLICATE_ID: New dispatch ID '$SupersedeByDispatchId' already exists at: $newFile"
        }

        $activeForIssue = @(Get-ActiveDispatchesForIssue -Dir $dir -IssueNumber $SupersedeIssueNumber)
        if ($activeForIssue.Count -ne 1 -or $activeForIssue[0].DispatchId -ne $SupersedeDispatchId) {
            throw "DISPATCH_SINGLETON_VIOLATION: Explicit Supersede requires exactly one active dispatch for Issue #$SupersedeIssueNumber and it must be '$SupersedeDispatchId'"
        }

        # Conservative crash order: old terminal first, then new active.
        # If step 2 fails after step 1 succeeds, no active dispatch exists
        # for this Issue — safer than two active dispatches. Operator
        # creates a brand-new dispatch with a new ID after revalidation.
        # Reactivating the old superseded dispatch is FORBIDDEN.

        # Step 1: Mark old dispatch as superseded (terminal)
        Update-DispatchState -FilePath $oldFile -NewState 'superseded'

        # Step 2: Create new dispatch as active
        try {
            return New-DispatchEnvelope -DispatchId $SupersedeByDispatchId `
                -IssueNumber $SupersedeIssueNumber -Driver $SupersedeByDriver `
                -SpecTaskId $SupersedeBySpecTaskId `
                -GovernanceVersion $SupersedeByGovernanceVersion `
                -AllowedPaths $normalizedAllowed -BaseSha $baseSha -AcHash $acHash `
                -CanonicalAcTextVersion 'v1' -Dir $dir
        } catch {
            Write-Verbose "DISPATCH: CRASH SCENARIO — old dispatch '$SupersedeDispatchId' is superseded but new dispatch '$SupersedeByDispatchId' creation failed. This Issue has no active dispatch. Operator must create a fresh dispatch with a new ID after revalidation. Never reactivate the old superseded dispatch."
            throw
        }
    }

    return $result
}

# ======================================================================
# Operation: Expire
# ======================================================================
function Invoke-Expire {
    Write-Verbose "DISPATCH: Expiring dispatch '$ExpireDispatchId' reason: $ExpirationReason"

    $dir = Get-DispatchDir -Path $StorePath
    $dispatchFile = Get-DispatchFilePath -Dir $dir -Id $ExpireDispatchId

    # --- Acquire lock and expire ---
    $result = Invoke-WithDispatchLock -Dir $dir -ScriptBlock {
        $dispatch = Read-DispatchFile -FilePath $dispatchFile

        if ([int]$dispatch.issue_number -ne $ExpireIssueNumber) {
            throw "DISPATCH_ISSUE_MISMATCH: Dispatch issue_number $($dispatch.issue_number) does not match expected $ExpireIssueNumber"
        }
        if ($dispatch.state -ne 'active') {
            throw "DISPATCH_INACTIVE: Dispatch '$ExpireDispatchId' is in state '$($dispatch.state)' and cannot be expired"
        }

        # Expire just sets state to 'expired' — no lifecycle metadata
        return Update-DispatchState -FilePath $dispatchFile -NewState 'expired'
    }

    return [PSCustomObject]@{
        ok = $true
        operation = 'expire'
        dispatch_id = $ExpireDispatchId
        state = 'expired'
        reason = $ExpirationReason
    }
}

# ======================================================================
# Main dispatch
# ======================================================================
try {
    switch ($PSCmdlet.ParameterSetName) {
        'Create' {
            Invoke-Create
        }
        'Validate' {
            Invoke-Validate
        }
        'Supersede' {
            Invoke-Supersede
        }
        'Expire' {
            Invoke-Expire
        }
        default {
            throw "DISPATCH_UNKNOWN_OPERATION: Unknown parameter set '$($PSCmdlet.ParameterSetName)'"
        }
    }
}
catch {
    Write-Error -Message "ERROR: $($_.Exception.Message)" -ErrorAction Continue
    exit 1
}
