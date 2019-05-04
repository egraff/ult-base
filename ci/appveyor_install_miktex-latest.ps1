$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path

$setupZipPath = "$scriptRoot\miktexsetup.zip"
(New-Object System.Net.WebClient).DownloadFile('http://ftp.rrze.uni-erlangen.de/ctan/systems/win32/miktex/setup/windows-x64/miktexsetup-2.9.6942-x64.zip', $setupZipPath)

Expand-Archive $setupZipPath -DestinationPath $scriptRoot -Force

$pkgDir = md "miktex-packages" -Force | %{ $_.FullName }

. "$scriptRoot\miktexsetup.exe" `
  download `
  --package-set=complete `
  --local-package-repository="$pkgDir" `
  --remote-package-repository=http://ftp.rrze.uni-erlangen.de/ctan/systems/win32/miktex/tm/packages/ `
  --verbose

$exitCode = $LastExitCode
if ($exitCode -ne 0)
{
  throw "Failed to download MiKTeX packages"
}

. "$scriptRoot\miktexsetup.exe" `
  install `
  --shared `
  --modify-path `
  --package-set=complete `
  --local-package-repository="$pkgDir" `
  --verbose

$exitCode = $LastExitCode
if ($exitCode -ne 0)
{
  throw "MiKTeX installer failed"
}

$env:Path = [System.Environment]::ExpandEnvironmentVariables(
    [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
    [System.Environment]::GetEnvironmentVariable('Path', 'User')
)
refreshenv

$ErrorActionPreference = "Continue"

mpm --admin --update-db
# mpm --admin --upgrade --package-level=basic
# mpm --admin --find-updates | foreach { $_.ToString() } | select-string "^(?!miktex.*$)" > upd-packages.txt
# mpm --admin --update-some=upd-packages.txt --verbose

initexmf --admin --enable-installer --verbose
initexmf --admin --default-paper-size=a4 --verbose
initexmf --admin --update-fndb --verbose
initexmf --admin --mkmaps --verbose

initexmf --enable-installer --verbose
initexmf --default-paper-size=a4 --verbose
initexmf --update-fndb --verbose
initexmf --mkmaps --verbose
