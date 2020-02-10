$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path

$installerPath = "$scriptRoot\basic-miktex-x64.exe"
$installerUrl = 'http://mirrors.rit.edu/CTAN/systems/win32/miktex/setup/windows-x64/basic-miktex-2.9.7342-x64.exe'

(New-Object System.Net.WebClient).DownloadFile($installerUrl, $installerPath)

$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = $installerPath
$pinfo.Arguments = "--unattended --shared --auto-install=yes --paper-size=A4"
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

mpm --admin --update-db --repository=http://ftp.rrze.uni-erlangen.de/ctan/systems/win32/miktex/tm/packages/ --verbose
mpm --admin --upgrade --package-level=basic --repository=http://ftp.rrze.uni-erlangen.de/ctan/systems/win32/miktex/tm/packages/ --verbose
mpm --admin --update --repository=http://ftp.rrze.uni-erlangen.de/ctan/systems/win32/miktex/tm/packages/ --verbose

initexmf --admin --enable-installer --verbose
initexmf --admin --default-paper-size=a4 --verbose
initexmf --admin --update-fndb --verbose
initexmf --admin --mkmaps --verbose


$OldErrorActionPreference = $ErrorActionPreference;
$ErrorActionPreference = "Continue";

# Manually register TEXMFHOME (see https://github.com/MiKTeX/miktex/issues/272)
initexmf --user-roots="${env:USERPROFILE}/texmf" 2>&1 | %{ "$_" }
$exitCode = $LastExitCode
$ErrorActionPreference = $OldErrorActionPreference;

if ($exitCode -ne 0) {
    throw "initexmf failed with exit code ${exitCode}"
}
