$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path

$installerPath = "$scriptRoot\ProTeXt-3.1.9-121317.exe"
(New-Object System.Net.WebClient).DownloadFile('http://ftp.math.utah.edu/pub/tex/historic/systems/protext/2018-3.1.9/ProTeXt-3.1.9-121317.exe', $installerPath)

$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = $installerPath
$pinfo.Arguments = "-dprotext -s"
$pinfo.RedirectStandardError = $true
$pinfo.RedirectStandardOutput = $true
$pinfo.UseShellExecute = $false
$pinfo.WorkingDirectory = $scriptRoot

Write-Host "Starting proTeXt installer"
$p = New-Object System.Diagnostics.Process
$p.StartInfo = $pinfo
$p.Start() | Out-Null

Write-Host "Waiting for proTeXt installer to finish..."

# Start async reads of output streams to avoid deadlock
$p.BeginOutputReadLine()
$p.BeginErrorReadLine()

$p.WaitForExit()
$exitCode = $p.ExitCode
Write-Host "proTeXt installer exited with code $exitCode"

if ($exitCode -ne 0)
{
  throw "proTeXt installer failed"
}

$protextDir = [string](Resolve-Path "$scriptRoot\protext")

$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = "${protextDir}\MiKTeX\setup\setup-2.9.6406-x64.exe"
$pinfo.Arguments = "--unattended --shared --package-set=complete --install-from-local-repository --local-package-repository='${protextDir}\MiKTeX\tm\packages' --auto-install=yes --paper-size=A4"
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
