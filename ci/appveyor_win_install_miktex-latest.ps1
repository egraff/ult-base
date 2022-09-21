$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path

$miktexMirror = 'https://mirrors.rit.edu/CTAN/systems/win32/miktex'

$installerPath = "$scriptRoot\basic-miktex-x64.exe"
$installerUrl = "${miktexMirror}/setup/windows-x64/basic-miktex-22.7-x64.exe"

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

initexmf --admin --enable-installer --verbose
initexmf --admin --default-paper-size=a4 --verbose
initexmf --admin --update-fndb --verbose
initexmf --admin --mkmaps --verbose


$OldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"

# Manually register TEXMFHOME (see https://github.com/MiKTeX/miktex/issues/272)
initexmf --user-roots="${env:USERPROFILE}/texmf" 2>&1 | %{ "$_" }
$exitCode = $LastExitCode
$ErrorActionPreference = $OldErrorActionPreference

if ($exitCode -ne 0) {
    throw "initexmf failed with exit code ${exitCode}"
}

mpm --admin --set-repository="${miktexMirror}/tm/packages/" --verbose

miktex --admin --verbose packages update-package-database --repository="${miktexMirror}/tm/packages/" 2>&1 | %{ "$_" }
miktex --admin --verbose packages upgrade --repository="${miktexMirror}/tm/packages/" basic 2>&1 | %{ "$_" }
miktex --admin --verbose packages update --repository="${miktexMirror}/tm/packages/" 2>&1 | %{ "$_" }
