$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path

$installerPath = "$scriptRoot\basic-miktex-x64.exe"
(New-Object System.Net.WebClient).DownloadFile('http://mirrors.rit.edu/CTAN/systems/win32/miktex/setup/windows-x64/basic-miktex-2.9.7031-x64.exe', $installerPath)

$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = $installerPath
$pinfo.Arguments = "--unattended --shared --package-set=complete --remote-package-repository=http://mirrors.rit.edu/CTAN/systems/win32/miktex/tm/packages --auto-install=yes --paper-size=A4"
$pinfo.RedirectStandardError = $true
$pinfo.RedirectStandardOutput = $true
$pinfo.UseShellExecute = $false
$pinfo.WorkingDirectory = $scriptRoot

Write-Host "Starting MiKTeX installer"
$p = New-Object System.Diagnostics.Process
$p.StartInfo = $pinfo
$p.Start() | Out-Null

Write-Host "Waiting for MiKTeX installer to finish..."

# Start async reads of output streams to avoid deadlock
$p.BeginOutputReadLine()
$p.BeginErrorReadLine()

$p.WaitForExit()
$exitCode = $p.ExitCode
Write-Host "MiKTeX installer exited with code $exitCode"

if ($exitCode -ne 0)
{
  throw "MiKTeX installer failed"
}

$env:Path = [System.Environment]::ExpandEnvironmentVariables(
    [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
    [System.Environment]::GetEnvironmentVariable('Path', 'User')
)
refreshenv

mpm --admin --update-db
# mpm --admin --upgrade --package-level=basic
# mpm --admin --find-updates | foreach { $_.ToString() } | select-string "^(?!miktex.*$)" > upd-packages.txt
# mpm --admin --update-some=upd-packages.txt --verbose

initexmf --admin --enable-installer --verbose
initexmf --admin --update-fndb --verbose
initexmf --admin --mkmaps --verbose
