param(
    [Parameter(Mandatory=$true)]
    [string]
    $Repository,

    [Parameter(Mandatory=$true)]
    [string]
    $ProfilePath
)

$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path

$profileFullPath = [string](Resolve-Path $ProfilePath)

$installZipPath = "$scriptRoot\install-tl.zip"
(New-Object System.Net.WebClient).DownloadFile("${Repository}/install-tl.zip", $installZipPath)

md "$scriptRoot\install-tl" -Force
Expand-Archive $installZipPath -DestinationPath "${scriptRoot}\install-tl"

$tl_dir = Get-ChildItem -Path "${scriptRoot}\install-tl" | ?{ $_.Name -like 'install-tl-*' } | Select-Object -ExpandProperty FullName -First 1

cmd /c "${tl_dir}\install-tl-windows.bat 2>&1" `
    -no-gui `
    -logfile install-tl.log `
    -repository "$Repository" `
    -profile "$profileFullPath"
