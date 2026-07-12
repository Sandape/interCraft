[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $ExpectedRepoRoot,

    [Parameter(Mandatory)]
    [string] $ExpectedBranch,

    [Parameter(Mandatory)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string] $ExpectedBaseSha,

    [string] $BaseRef = 'origin/master',

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string[]] $AllowedPath,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string[]] $TargetPath,

    [switch] $AllowDirtyWithinAllowedPaths,
    [switch] $OutputJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Stop-Preflight {
    param(
        [Parameter(Mandatory)]
        [string] $Code,

        [Parameter(Mandatory)]
        [string] $Message
    )

    throw "PREFLIGHT_FAILED:${Code}: $Message"
}

function Invoke-GitRead {
    param(
        [Parameter(Mandatory)]
        [string[]] $Arguments
    )

    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & git @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }

    if ($exitCode -ne 0) {
        throw "git $($Arguments -join ' ') failed: $($output -join [Environment]::NewLine)"
    }
    return @($output | ForEach-Object { $_.ToString() })
}

function Get-NormalizedAbsolutePath {
    param([Parameter(Mandatory)][string] $Path)

    return [IO.Path]::GetFullPath($Path).TrimEnd([char[]]@('\', '/'))
}

function ConvertTo-RepositoryPath {
    param(
        [Parameter(Mandatory)]
        [string] $Path,

        [Parameter(Mandatory)]
        [string] $ErrorCode,

        [switch] $AllowDirectoryGlob
    )

    $candidate = $Path.Trim().Replace('\', '/')
    while ($candidate.StartsWith('./', [StringComparison]::Ordinal)) {
        $candidate = $candidate.Substring(2)
    }

    $containsControlCharacter = @($candidate.ToCharArray() | Where-Object {
        ([int]$_ -lt 32) -or ([int]$_ -eq 127)
    }).Count -gt 0
    if ([string]::IsNullOrWhiteSpace($candidate) -or
        $containsControlCharacter -or
        $candidate.Contains(':') -or
        [IO.Path]::IsPathRooted($candidate) -or
        $candidate -match '^[A-Za-z]:' -or
        $candidate.StartsWith('/', [StringComparison]::Ordinal)) {
        Stop-Preflight -Code $ErrorCode -Message "Path must be repository-relative: '$Path'"
    }

    $isDirectoryGlob = $AllowDirectoryGlob -and $candidate.EndsWith('/**', [StringComparison]::Ordinal)
    $pathPortion = if ($isDirectoryGlob) { $candidate.Substring(0, $candidate.Length - 3) } else { $candidate }

    if ($candidate.IndexOfAny([char[]]@('*', '?', '[', ']')) -ge 0 -and -not $isDirectoryGlob) {
        Stop-Preflight -Code $ErrorCode -Message "Only an exact path or a trailing '/**' directory glob is allowed: '$Path'"
    }
    if ($isDirectoryGlob -and $pathPortion.IndexOfAny([char[]]@('*', '?', '[', ']')) -ge 0) {
        Stop-Preflight -Code $ErrorCode -Message "Wildcard characters are not allowed before a trailing '/**': '$Path'"
    }

    $segments = @($pathPortion.Split('/') | Where-Object { $_ -ne '' })
    $containsTraversal = @($segments | Where-Object { $_ -eq '.' -or $_ -eq '..' }).Count -gt 0
    $targetsGitMetadata = $segments.Count -gt 0 -and $segments[0].Equals('.git', [StringComparison]::OrdinalIgnoreCase)
    if ($segments.Count -eq 0 -or $containsTraversal -or $targetsGitMetadata) {
        Stop-Preflight -Code $ErrorCode -Message "Path traversal and empty paths are forbidden: '$Path'"
    }

    $normalized = $segments -join '/'
    if ($isDirectoryGlob) {
        return "$normalized/**"
    }
    return $normalized
}

function Test-PathAllowed {
    param(
        [Parameter(Mandatory)]
        [string] $Path,

        [Parameter(Mandatory)]
        [string[]] $Allowed
    )

    foreach ($rule in $Allowed) {
        if ($rule.EndsWith('/**', [StringComparison]::Ordinal)) {
            $prefix = $rule.Substring(0, $rule.Length - 3)
            if ($Path.Equals($prefix, [StringComparison]::OrdinalIgnoreCase) -or
                $Path.StartsWith("$prefix/", [StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
        }
        elseif ($Path.Equals($rule, [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Get-DirtyPaths {
    $statusLines = @(Invoke-GitRead -Arguments @('-c', 'core.quotepath=false', 'status', '--porcelain=v1', '--untracked-files=all'))
    $paths = New-Object 'System.Collections.Generic.List[string]'

    foreach ($line in $statusLines) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line.Length -lt 4) {
            Stop-Preflight -Code 'DIRTY_STATUS_UNPARSEABLE' -Message "Unexpected git status record: '$line'"
        }

        $path = $line.Substring(3)
        $renameSeparator = $path.LastIndexOf(' -> ', [StringComparison]::Ordinal)
        if ($renameSeparator -ge 0) {
            $path = $path.Substring($renameSeparator + 4)
        }
        if ($path.StartsWith('"', [StringComparison]::Ordinal)) {
            Stop-Preflight -Code 'DIRTY_STATUS_UNPARSEABLE' -Message 'Quoted or control-character file names require manual review'
        }
        $paths.Add((ConvertTo-RepositoryPath -Path $path -ErrorCode 'DIRTY_STATUS_UNPARSEABLE'))
    }

    return @($paths | Sort-Object -Unique)
}

$actualRootRaw = (Invoke-GitRead -Arguments @('rev-parse', '--show-toplevel') | Select-Object -Last 1)
$actualRoot = Get-NormalizedAbsolutePath -Path $actualRootRaw
$expectedRoot = Get-NormalizedAbsolutePath -Path $ExpectedRepoRoot
if (-not $actualRoot.Equals($expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    Stop-Preflight -Code 'REPO_ROOT_MISMATCH' -Message "Expected '$expectedRoot', found '$actualRoot'"
}

try {
    $actualBranch = (Invoke-GitRead -Arguments @('symbolic-ref', '--quiet', '--short', 'HEAD') | Select-Object -Last 1).Trim()
}
catch {
    Stop-Preflight -Code 'DETACHED_HEAD' -Message 'A named feature branch is required'
}
if ($actualBranch -eq 'master' -or $actualBranch -eq 'main') {
    Stop-Preflight -Code 'PROTECTED_BRANCH' -Message "Writes are forbidden on protected branch '$actualBranch'"
}
if (-not $actualBranch.Equals($ExpectedBranch, [StringComparison]::Ordinal)) {
    Stop-Preflight -Code 'BRANCH_MISMATCH' -Message "Expected '$ExpectedBranch', found '$actualBranch'"
}

$expectedBase = $ExpectedBaseSha.ToLowerInvariant()
try {
    $actualBaseRef = (Invoke-GitRead -Arguments @('rev-parse', $BaseRef) | Select-Object -Last 1).Trim().ToLowerInvariant()
}
catch {
    Stop-Preflight -Code 'BASE_REF_MISSING' -Message "Cannot resolve base ref '$BaseRef'"
}
if ($actualBaseRef -ne $expectedBase) {
    Stop-Preflight -Code 'BASE_SHA_MISMATCH' -Message "Expected $BaseRef at '$expectedBase', found '$actualBaseRef'"
}

try {
    $mergeBase = (Invoke-GitRead -Arguments @('merge-base', 'HEAD', $expectedBase) | Select-Object -Last 1).Trim().ToLowerInvariant()
}
catch {
    Stop-Preflight -Code 'BASE_SHA_MISMATCH' -Message "Expected base '$expectedBase' is not available in this worktree"
}
if ($mergeBase -ne $expectedBase) {
    Stop-Preflight -Code 'BASE_SHA_MISMATCH' -Message "Branch is not based on expected SHA '$expectedBase'"
}

$normalizedAllowed = @($AllowedPath | ForEach-Object {
    ConvertTo-RepositoryPath -Path $_ -ErrorCode 'INVALID_ALLOWED_PATH' -AllowDirectoryGlob
} | Sort-Object -Unique)
$normalizedTargets = @($TargetPath | ForEach-Object {
    ConvertTo-RepositoryPath -Path $_ -ErrorCode 'INVALID_TARGET_PATH'
} | Sort-Object -Unique)

foreach ($target in $normalizedTargets) {
    if (-not (Test-PathAllowed -Path $target -Allowed $normalizedAllowed)) {
        Stop-Preflight -Code 'TARGET_NOT_ALLOWED' -Message "Target '$target' is outside the dispatch allowlist"
    }
}

$dirtyPaths = @(Get-DirtyPaths)
if ($dirtyPaths.Count -gt 0 -and -not $AllowDirtyWithinAllowedPaths) {
    Stop-Preflight -Code 'DIRTY_WORKTREE' -Message "Worktree is dirty: $($dirtyPaths -join ', ')"
}
if ($AllowDirtyWithinAllowedPaths) {
    foreach ($dirtyPath in $dirtyPaths) {
        if (-not (Test-PathAllowed -Path $dirtyPath -Allowed $normalizedAllowed)) {
            Stop-Preflight -Code 'DIRTY_PATH_ESCAPE' -Message "Dirty path '$dirtyPath' is outside the dispatch allowlist"
        }
    }
}

$headSha = (Invoke-GitRead -Arguments @('rev-parse', 'HEAD') | Select-Object -Last 1).Trim().ToLowerInvariant()
$result = [ordered]@{
    ok = $true
    repo_root = $actualRoot
    branch = $actualBranch
    head_sha = $headSha
    base_ref = $BaseRef
    base_sha = $expectedBase
    allowed_paths = $normalizedAllowed
    target_paths = $normalizedTargets
    dirty_paths = $dirtyPaths
    dirty_mode = if ($AllowDirtyWithinAllowedPaths) { 'allowlisted-only' } else { 'clean-required' }
}

if ($OutputJson) {
    $result | ConvertTo-Json -Depth 5 -Compress
}
else {
    [pscustomobject]$result
}
