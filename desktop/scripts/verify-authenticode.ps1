param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[0-9A-Fa-f]{64}$')]
  [string] $ExpectedSignerSha256,

  [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
  [string[]] $TargetPath
)

$ErrorActionPreference = 'Stop'

if ($TargetPath.Count -eq 0) {
  throw 'At least one Authenticode target is required'
}

$expectedFingerprint = $ExpectedSignerSha256.ToUpperInvariant()

foreach ($path in $TargetPath) {
  $signature = Get-AuthenticodeSignature -LiteralPath $path
  if ($signature.Status -ne 'Valid') {
    throw (
      'Invalid Authenticode signature for {0}: {1}' -f
      $path,
      $signature.Status
    )
  }
  if ($null -eq $signature.SignerCertificate) {
    throw "Authenticode signer certificate is missing for $path"
  }
  $actualFingerprint = $signature.SignerCertificate.GetCertHashString(
    [System.Security.Cryptography.HashAlgorithmName]::SHA256
  ).ToUpperInvariant()
  if ($actualFingerprint -ne $expectedFingerprint) {
    throw (
      'Unexpected Authenticode signer for {0}: expected {1}, received {2}' -f
      $path,
      $expectedFingerprint,
      $actualFingerprint
    )
  }
  if ($null -eq $signature.TimeStamperCertificate) {
    throw "Authenticode timestamp certificate is missing for $path"
  }
}
