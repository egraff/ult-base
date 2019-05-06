$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path

$installZipPath = "$scriptRoot\install-tl.zip"
(New-Object System.Net.WebClient).DownloadFile('http://mirrors.rit.edu/CTAN/systems/texlive/tlnet/install-tl.zip', $installZipPath)

md "$scriptRoot\install-tl" -Force
Expand-Archive $installZipPath -DestinationPath "$scriptRoot\install-tl"

$tl_dir = Get-ChildItem -Path "$scriptRoot\install-tl" | ?{ $_.Name -like 'install-tl-*' } | Select-Object -ExpandProperty FullName -First 1

$profilePath = [string](Resolve-Path $scriptRoot\..\texlive-win.profile)

cmd /c "${tl_dir}\install-tl-windows.bat 2>&1" `
  -no-gui `
  -logfile install-tl.log `
  -repository http://mirrors.rit.edu/CTAN/systems/texlive/tlnet `
  -profile "$profilePath"
