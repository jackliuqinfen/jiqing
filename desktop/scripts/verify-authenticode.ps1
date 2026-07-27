param(
  [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
  [string[]] $TargetPath
)

$ErrorActionPreference = 'Stop'

if ($TargetPath.Count -eq 0) {
  throw 'At least one Authenticode target is required'
}

foreach ($path in $TargetPath) {
  $signature = Get-AuthenticodeSignature -LiteralPath $path
  if ($signature.Status -ne 'Valid') {
    throw (
      'Invalid Authenticode signature for {0}: {1}' -f
      $path,
      $signature.Status
    )
  }
}
