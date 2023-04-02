param(
    [Parameter(Mandatory=$true)]
    [string]
    $Repository,

    [Parameter(Mandatory=$true)]
    [string]
    $ProfilePath
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path

$profileFullPath = [string](Resolve-Path $ProfilePath)

[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
$installZipPath = "$scriptRoot\install-tl.zip"


for ($attempt = 0; $attempt -lt 5; $attempt++)
{
  $client = New-Object System.Net.WebClient
  try
  {
    $client.DownloadFile("${Repository}/install-tl.zip", $installZipPath)
  }
  catch [System.Net.WebException]
  {
    continue
  }
  finally
  {
    $client.Dispose()
  }

  break
}

md "$scriptRoot\install-tl" -Force
Expand-Archive $installZipPath -DestinationPath "${scriptRoot}\install-tl"

$tl_dir = Get-ChildItem -Path "${scriptRoot}\install-tl" | ?{ $_.Name -like 'install-tl-*' } | Select-Object -ExpandProperty FullName -First 1

cmd /c "echo ^M | ${tl_dir}\install-tl-windows.bat 2>&1" `
    -no-gui `
    -logfile install-tl.log `
    -repository "$Repository" `
    -profile "$profileFullPath"
