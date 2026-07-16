<#
.SYNOPSIS
    Trusted pull_request_target wrapper for the read-only PR governance gate.

.DESCRIPTION
    This script is executed only from the exact, authoritative master checkout
    selected by the workflow. It reads the PR and its head dispatch envelope
    through authenticated GitHub API calls, stages only the dispatch JSON beside
    trusted copies of gate.ps1/dispatch.ps1, and invokes the existing gate.

    The PR head is never checked out and no PR-controlled script is executed.
    Any malformed, missing, stale, racing, or transport-uncertain input fails
    closed. Artifacts contain only bounded metadata and sanitized messages.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateRange(1, [int]::MaxValue)]
    [int] $PRNumber,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $Owner,

    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $Repo,

    [Parameter(Mandatory)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string] $ExpectedMasterSha,

    [string] $ArtifactDir = (Join-Path (Get-Location) 'governance-gate-artifacts')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$MAX_API_BYTES = 512KB
$MAX_DISPATCH_BYTES = 64KB
$MAX_CHANGED_PATHS = 10000
$MAX_ARTIFACT_TEXT = 16000
$SAFE_ID_PATTERN = '^[a-z0-9][a-z0-9._-]*$'

$script:artifactDir = [IO.Path]::GetFullPath($ArtifactDir)
$script:stageDir = $null
$script:prSnapshot = $null
$script:dispatchMeta = $null
$script:changedPaths = @()
$script:gateResult = [ordered]@{ passed = $false; failed_check = 'GATE_TRUSTED_RUNNER_FAILED'; message = 'Trusted runner did not complete' }

function ConvertTo-SafeText {
    param([AllowNull()][string] $Text)
    if ($null -eq $Text) { return '' }
    $safe = $Text -replace '(?i)(authorization|cookie|password|token|secret|api[_-]?key|postgres(?:ql)?://|redis://)\s*[:=]?\s*[^\s,;]+', '[REDACTED]'
    $safe = $safe -replace '[\r\n]+', ' '
    if ($safe.Length -gt $MAX_ARTIFACT_TEXT) { return $safe.Substring(0, $MAX_ARTIFACT_TEXT) + '...' }
    return $safe
}

function Stop-TrustedGate {
    param([Parameter(Mandatory)][string] $Code, [Parameter(Mandatory)][string] $Message)
    throw ("{0}: {1}" -f $Code, (ConvertTo-SafeText $Message))
}

function Assert-SafeRepositoryIdentity {
    param([Parameter(Mandatory)][string] $Value, [Parameter(Mandatory)][string] $Name)
    if ($Value -notmatch '^[A-Za-z0-9_.-]+$') {
        Stop-TrustedGate -Code 'GATE_INVALID_TARGET' -Message "$Name is not a safe repository identifier"
    }
}

function Invoke-GhApi {
    param([Parameter(Mandatory)][string[]] $Arguments)
    try {
        $output = & gh @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    catch {
        Stop-TrustedGate -Code 'GATE_TRANSPORT_FAILURE' -Message "Unable to start gh: $($_.Exception.Message)"
    }
    $raw = @($output | ForEach-Object { "$_" }) -join "`n"
    if ($exitCode -ne 0) {
        Stop-TrustedGate -Code 'GATE_TRANSPORT_FAILURE' -Message "gh request failed (exit $exitCode): $raw"
    }
    if ([Text.Encoding]::UTF8.GetByteCount($raw) -gt $MAX_API_BYTES) {
        Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message 'GitHub API response exceeded the bounded response size'
    }
    if ([string]::IsNullOrWhiteSpace($raw)) {
        Stop-TrustedGate -Code 'GATE_TRANSPORT_FAILURE' -Message 'GitHub API returned an empty response'
    }
    return $raw
}

function ConvertFrom-GhJson {
    param([Parameter(Mandatory)][string] $Raw, [Parameter(Mandatory)][string] $Context)
    try { return ($Raw | ConvertFrom-Json -ErrorAction Stop) }
    catch { Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message "$Context is not valid JSON" }
}

function Get-RequiredProperty {
    param([Parameter(Mandatory)] $Object, [Parameter(Mandatory)][string] $Name, [Parameter(Mandatory)][string] $Context)
    if ($null -eq $Object -or -not ($Object.PSObject.Properties.Name -contains $Name)) {
        Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message "$Context is missing required property '$Name'"
    }
    return $Object.$Name
}

function Assert-Sha {
    param([Parameter(Mandatory)][string] $Value, [Parameter(Mandatory)][string] $Name)
    if ($Value -cnotmatch '^[0-9a-f]{40}$') {
        Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message "$Name is not a 40-character SHA"
    }
}

function Get-DispatchIdFromBody {
    param([Parameter(Mandatory)][string] $Body)
    $matches = [regex]::Matches($Body, '(?m)^\s*(?:[-*]\s*)?\*\*Dispatch ID\*\*\s*:\s*(.*?)\s*$')
    if ($matches.Count -ne 1) {
        Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'PR body must contain exactly one canonical Dispatch ID field'
    }
    $id = $matches[0].Groups[1].Value.Trim()
    if ($id.StartsWith('`', [StringComparison]::Ordinal) -and $id.EndsWith('`', [StringComparison]::Ordinal) -and $id.Length -ge 2) {
        $id = $id.Substring(1, $id.Length - 2)
    }
    if ($id -notmatch $SAFE_ID_PATTERN -or $id.Length -gt 120) {
        Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'PR Dispatch ID is not a canonical bounded identifier'
    }
    return $id
}

function Get-IssueNumberFromBody {
    param([Parameter(Mandatory)][string] $Body)
    $matches = [regex]::Matches($Body, '(?m)^\s*Refs\s+#([1-9][0-9]*)\s*$')
    if ($matches.Count -ne 1) {
        Stop-TrustedGate -Code 'GATE_MISSING_ISSUE_REF' -Message 'PR body must contain exactly one canonical Refs #N line'
    }
    return [int]$matches[0].Groups[1].Value
}

function Get-HeadRepository {
    param([Parameter(Mandatory)] $PullRequest)
    $head = Get-RequiredProperty -Object $PullRequest -Name 'head' -Context 'pull request'
    $headRepo = Get-RequiredProperty -Object $head -Name 'repo' -Context 'pull request head'
    $fullName = [string](Get-RequiredProperty -Object $headRepo -Name 'full_name' -Context 'pull request head repository')
    if ($fullName -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') {
        Stop-TrustedGate -Code 'GATE_PR_HEAD_RACE' -Message 'PR head repository is missing or malformed (fork may have been deleted)'
    }
    return $fullName
}

function Get-BlobSha {
    param([Parameter(Mandatory)][byte[]] $Bytes)
    $header = [Text.Encoding]::ASCII.GetBytes("blob $($Bytes.Length)`0")
    $payload = New-Object byte[] ($header.Length + $Bytes.Length)
    [Array]::Copy($header, 0, $payload, 0, $header.Length)
    [Array]::Copy($Bytes, 0, $payload, $header.Length, $Bytes.Length)
    $hash = [Security.Cryptography.SHA1]::Create().ComputeHash($payload)
    return (($hash | ForEach-Object { $_.ToString('x2') }) -join '')
}

function Read-DispatchFromHead {
    param([Parameter(Mandatory)][string] $HeadRepository, [Parameter(Mandatory)][string] $HeadSha, [Parameter(Mandatory)][string] $DispatchId)
    # DispatchId is already constrained to a filename-safe identifier. Keep
    # repository path separators literal; GitHub's Contents API does not
    # resolve an encoded slash (`%2F`) as a directory separator.
    $endpoint = "repos/$HeadRepository/contents/.github/dispatches/$DispatchId.json?ref=$HeadSha"
    $content = ConvertFrom-GhJson -Raw (Invoke-GhApi -Arguments @('api', $endpoint)) -Context 'dispatch Contents API response'

    $type = [string](Get-RequiredProperty -Object $content -Name 'type' -Context 'dispatch Contents API response')
    $encoding = [string](Get-RequiredProperty -Object $content -Name 'encoding' -Context 'dispatch Contents API response')
    $name = [string](Get-RequiredProperty -Object $content -Name 'name' -Context 'dispatch Contents API response')
    $path = [string](Get-RequiredProperty -Object $content -Name 'path' -Context 'dispatch Contents API response')
    $blobSha = [string](Get-RequiredProperty -Object $content -Name 'sha' -Context 'dispatch Contents API response')
    $sizeRaw = Get-RequiredProperty -Object $content -Name 'size' -Context 'dispatch Contents API response'
    [int64]$size = 0
    if (-not [int64]::TryParse([string]$sizeRaw, [Globalization.NumberStyles]::Integer, [Globalization.CultureInfo]::InvariantCulture, [ref]$size)) {
        Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message 'Dispatch Contents API size is not an integer'
    }
    $encoded = [string](Get-RequiredProperty -Object $content -Name 'content' -Context 'dispatch Contents API response')

    if ($type -cne 'file' -or $encoding -cne 'base64' -or $name -cne "$DispatchId.json" -or $path -cne ".github/dispatches/$DispatchId.json") {
        Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'Contents API did not return the exact dispatch file'
    }
    Assert-Sha -Value $blobSha -Name 'dispatch blob SHA'
    if ($size -lt 1 -or $size -gt $MAX_DISPATCH_BYTES) {
        Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'Dispatch envelope exceeds the bounded size limit'
    }
    try {
        $bytes = [Convert]::FromBase64String(($encoded -replace '\s', ''))
    }
    catch {
        Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message 'Dispatch Contents API content is not valid base64'
    }
    if ($bytes.Length -ne $size) {
        Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message 'Dispatch content length does not match Contents API size'
    }
    if ((Get-BlobSha -Bytes $bytes) -cne $blobSha) {
        Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message 'Dispatch blob SHA does not match decoded content'
    }
    try {
        $jsonText = (New-Object Text.UTF8Encoding($false, $true)).GetString($bytes)
        $envelope = $jsonText | ConvertFrom-Json -ErrorAction Stop
    }
    catch { Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message 'Dispatch content is not valid UTF-8 JSON' }

    $required = @('dispatch_id','issue_number','driver','base_sha','spec_task_id','ac_hash','canonical_ac_text_version','allowed_paths','governance_version','created_at','state')
    foreach ($field in $required) { [void](Get-RequiredProperty -Object $envelope -Name $field -Context 'dispatch envelope') }
    $propertyNames = @($envelope.PSObject.Properties.Name)
    foreach ($field in $propertyNames) {
        if ($required -notcontains $field) { Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message "Dispatch envelope contains unknown field '$field'" }
    }
    if ([string]$envelope.dispatch_id -cne $DispatchId -or [string]$envelope.state -cne 'active') {
        Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'Dispatch envelope ID or state is invalid'
    }
    [int]$envelopeIssueNumber = 0
    if (-not [int]::TryParse([string]$envelope.issue_number, [Globalization.NumberStyles]::Integer, [Globalization.CultureInfo]::InvariantCulture, [ref]$envelopeIssueNumber) -or $envelopeIssueNumber -le 0) {
        Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'Dispatch Issue number is invalid'
    }
    Assert-Sha -Value ([string]$envelope.base_sha) -Name 'dispatch base SHA'
    if ([string]$envelope.ac_hash -notmatch '^[0-9a-f]{64}$') { Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'Dispatch AC hash is invalid' }
    if (-not ($envelope.allowed_paths -is [Array])) { Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'Dispatch allowed_paths must be an array' }
    $paths = @($envelope.allowed_paths)
    if ($paths.Count -lt 1 -or $paths.Count -gt 100) { Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'Dispatch allowed_paths is invalid' }
    foreach ($p in $paths) { if ([string]$p -notmatch '^[^\x00-\x1f\x7f:]+$' -or ([string]$p).Length -gt 256) { Stop-TrustedGate -Code 'GATE_DISPATCH_REF_MALFORMED' -Message 'Dispatch allowed_paths contains an unsafe value' } }

    return [pscustomobject]@{ Bytes = $bytes; Text = $jsonText; Envelope = $envelope; BlobSha = $blobSha; Size = $size; SourceRepository = $HeadRepository; SourceSha = $HeadSha; ApiPath = $path }
}

function Write-JsonFile {
    param([Parameter(Mandatory)][string] $Path, [Parameter(Mandatory)] $Value)
    $Value | ConvertTo-Json -Depth 8 -Compress | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Write-Artifacts {
    New-Item -ItemType Directory -Path $script:artifactDir -Force | Out-Null
    Write-JsonFile -Path (Join-Path $script:artifactDir 'gate-result.json') -Value $script:gateResult
    Write-JsonFile -Path (Join-Path $script:artifactDir 'changed-paths.json') -Value @($script:changedPaths)
    $manifest = [ordered]@{
        trusted_master_sha = $ExpectedMasterSha.ToLowerInvariant()
        pr_number = $PRNumber
        pr_head_sha = if ($null -ne $script:prSnapshot) { $script:prSnapshot.HeadSha } else { $null }
        pr_head_repository = if ($null -ne $script:prSnapshot) { $script:prSnapshot.HeadRepository } else { $null }
        dispatch_id = if ($null -ne $script:dispatchMeta) { $script:dispatchMeta.Envelope.dispatch_id } else { $null }
        dispatch_blob_sha = if ($null -ne $script:dispatchMeta) { $script:dispatchMeta.BlobSha } else { $null }
        dispatch_size = if ($null -ne $script:dispatchMeta) { $script:dispatchMeta.Size } else { $null }
        dispatch_source_sha = if ($null -ne $script:dispatchMeta) { $script:dispatchMeta.SourceSha } else { $null }
    }
    Write-JsonFile -Path (Join-Path $script:artifactDir 'staging-manifest.json') -Value $manifest
    $safeLog = ConvertTo-SafeText ("trusted_master_sha=$($manifest.trusted_master_sha); pr_number=$PRNumber; dispatch_id=$($manifest.dispatch_id); passed=$($script:gateResult.passed); failed_check=$($script:gateResult.failed_check)")
    Set-Content -LiteralPath (Join-Path $script:artifactDir 'trusted-gate.log') -Value $safeLog -Encoding UTF8
}

function Read-ChangedPaths {
    $lines = Invoke-GhApi -Arguments @('api', "repos/$Owner/$Repo/pulls/$PRNumber/files?per_page=100", '--paginate', '--jq', '.[]')
    foreach ($line in @($lines -split "`n" | Where-Object { $_.Trim() })) {
        if ($script:changedPaths.Count -ge $MAX_CHANGED_PATHS) {
            Stop-TrustedGate -Code 'GATE_PAGINATION_AMBIGUOUS' -Message 'Changed-file collection exceeded the safety cap'
        }
        try {
            $entry = $line | ConvertFrom-Json -ErrorAction Stop
            $filename = [string](Get-RequiredProperty -Object $entry -Name 'filename' -Context 'changed file entry')
            $status = [string](Get-RequiredProperty -Object $entry -Name 'status' -Context 'changed file entry')
            if ([string]::IsNullOrWhiteSpace($filename)) { Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message 'Changed file entry has an empty filename' }
            $script:changedPaths += [ordered]@{ filename = $filename; status = $status }
        }
        catch {
            if ($_.Exception.Message -match '^GATE_') { throw }
            Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message 'Changed-file API returned malformed JSON'
        }
    }
}

function Invoke-TrustedGate {
    Assert-SafeRepositoryIdentity -Value $Owner -Name 'Owner'
    Assert-SafeRepositoryIdentity -Value $Repo -Name 'Repo'
    Assert-Sha -Value $ExpectedMasterSha.ToLowerInvariant() -Name 'expected master SHA'

    $actualHead = (& git rev-parse HEAD 2>$null).Trim()
    if ($LASTEXITCODE -ne 0) { Stop-TrustedGate -Code 'GATE_BASE_NOT_AUTHORITATIVE' -Message 'Trusted checkout is not a git repository' }
    Assert-Sha -Value $actualHead.ToLowerInvariant() -Name 'trusted checkout HEAD'
    if ($actualHead.ToLowerInvariant() -cne $ExpectedMasterSha.ToLowerInvariant()) {
        Stop-TrustedGate -Code 'GATE_BASE_NOT_AUTHORITATIVE' -Message 'Trusted checkout HEAD is not the expected authoritative master SHA'
    }

    $pr = ConvertFrom-GhJson -Raw (Invoke-GhApi -Arguments @('api', "repos/$Owner/$Repo/pulls/$PRNumber")) -Context 'pull request response'
    $returnedNumber = [int](Get-RequiredProperty -Object $pr -Name 'number' -Context 'pull request')
    if ($returnedNumber -ne $PRNumber) { Stop-TrustedGate -Code 'GATE_INVALID_TARGET' -Message 'GitHub API returned a different pull request number' }
    $state = [string](Get-RequiredProperty -Object $pr -Name 'state' -Context 'pull request')
    $base = Get-RequiredProperty -Object $pr -Name 'base' -Context 'pull request'
    $baseRef = [string](Get-RequiredProperty -Object $base -Name 'ref' -Context 'pull request base')
    $baseSha = [string](Get-RequiredProperty -Object $base -Name 'sha' -Context 'pull request base')
    $head = Get-RequiredProperty -Object $pr -Name 'head' -Context 'pull request'
    $headSha = [string](Get-RequiredProperty -Object $head -Name 'sha' -Context 'pull request head')
    if ($state -cne 'open' -or $baseRef -cne 'master') { Stop-TrustedGate -Code 'GATE_INVALID_TARGET' -Message 'PR is not open against master' }
    Assert-Sha -Value $baseSha.ToLowerInvariant() -Name 'PR base SHA'
    Assert-Sha -Value $headSha.ToLowerInvariant() -Name 'PR head SHA'
    $headRepository = Get-HeadRepository -PullRequest $pr
    $body = [string](Get-RequiredProperty -Object $pr -Name 'body' -Context 'pull request')
    $issueNumber = Get-IssueNumberFromBody -Body $body
    $dispatchId = Get-DispatchIdFromBody -Body $body

    $script:prSnapshot = [pscustomobject]@{ HeadSha = $headSha.ToLowerInvariant(); HeadRepository = $headRepository; BaseSha = $baseSha.ToLowerInvariant() }
    $script:dispatchMeta = Read-DispatchFromHead -HeadRepository $headRepository -HeadSha $headSha.ToLowerInvariant() -DispatchId $dispatchId
    if ([int]$script:dispatchMeta.Envelope.issue_number -ne $issueNumber) {
        Stop-TrustedGate -Code 'GATE_MISSING_ISSUE_REF' -Message 'Dispatch Issue number does not match PR Refs #N'
    }
    Read-ChangedPaths

    $script:stageDir = Join-Path ([IO.Path]::GetTempPath()) ("intercraft-trusted-gate-{0}" -f [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Join-Path $script:stageDir 'scripts/governance') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $script:stageDir '.github/dispatches') -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'gate.ps1') -Destination (Join-Path $script:stageDir 'scripts/governance/gate.ps1')
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'dispatch.ps1') -Destination (Join-Path $script:stageDir 'scripts/governance/dispatch.ps1')
    [IO.File]::WriteAllBytes((Join-Path $script:stageDir ".github/dispatches/$dispatchId.json"), $script:dispatchMeta.Bytes)

    $childHost = @('pwsh','powershell.exe') | ForEach-Object { Get-Command -Name $_ -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1 } | Select-Object -First 1
    if ($null -eq $childHost) { Stop-TrustedGate -Code 'GATE_DISPATCH_VALIDATION_FAILED' -Message 'No PowerShell child host is available' }
    Push-Location $script:stageDir
    try {
        $gateOutput = & $childHost.Source -NoProfile -File (Join-Path $script:stageDir 'scripts/governance/gate.ps1') -PRNumber $PRNumber -DispatchId $dispatchId -Owner $Owner -Repo $Repo 2>&1
        $gateExit = $LASTEXITCODE
    }
    finally { Pop-Location }
    $gateText = @($gateOutput | ForEach-Object { "$_" })
    if ($gateExit -ne 0) {
        $last = ($gateText | Where-Object { $_ -match '^\s*\{' } | Select-Object -Last 1)
        if ($last) { try { $script:gateResult = ConvertFrom-GhJson -Raw $last -Context 'trusted gate result' } catch { } }
        Stop-TrustedGate -Code 'GATE_TRUSTED_GATE_FAILED' -Message 'Authoritative gate rejected the PR'
    }
    $lastPass = ($gateText | Where-Object { $_ -match '^\s*\{' } | Select-Object -Last 1)
    if (-not $lastPass) { Stop-TrustedGate -Code 'GATE_JSON_PARSE_FAILED' -Message 'Trusted gate did not emit a structured result' }
    $script:gateResult = ConvertFrom-GhJson -Raw $lastPass -Context 'trusted gate result'
    if (-not [bool]$script:gateResult.passed) { Stop-TrustedGate -Code 'GATE_TRUSTED_GATE_FAILED' -Message 'Authoritative gate returned passed=false' }

    $prAfter = ConvertFrom-GhJson -Raw (Invoke-GhApi -Arguments @('api', "repos/$Owner/$Repo/pulls/$PRNumber")) -Context 'pull request race check response'
    $afterHead = Get-RequiredProperty -Object (Get-RequiredProperty -Object $prAfter -Name 'head' -Context 'pull request race check') -Name 'sha' -Context 'pull request race check head'
    $afterRepo = Get-HeadRepository -PullRequest $prAfter
    if ([string]$afterHead -cne $script:prSnapshot.HeadSha -or $afterRepo -cne $script:prSnapshot.HeadRepository) {
        Stop-TrustedGate -Code 'GATE_PR_HEAD_RACE' -Message 'PR head changed while the trusted gate was running'
    }
    $script:gateResult = [ordered]@{ passed = $true }
}

try { Invoke-TrustedGate }
catch {
    if ($script:gateResult.passed -ne $true) {
        $raw = "$($_.Exception.Message)"
        $parts = $raw -split ':', 2
        $code = if ($parts.Count -eq 2 -and $parts[0] -match '^GATE_[A-Z0-9_]+$') { $parts[0] } else { 'GATE_TRUSTED_RUNNER_FAILED' }
        $message = if ($parts.Count -eq 2) { $parts[1].Trim() } else { $raw }
        $script:gateResult = [ordered]@{ passed = $false; failed_check = $code; message = ConvertTo-SafeText $message }
    }
}
finally {
    try { Write-Artifacts } catch { }
    if ($null -ne $script:stageDir -and (Test-Path -LiteralPath $script:stageDir)) { Remove-Item -LiteralPath $script:stageDir -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Output ($script:gateResult | ConvertTo-Json -Compress)
if (-not [bool]$script:gateResult.passed) { exit 1 }
exit 0
