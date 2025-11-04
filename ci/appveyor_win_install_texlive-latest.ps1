$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path
. "${scriptRoot}\install_texlive_windows.ps1" `
    -Repository 'http://mirrors.rit.edu/CTAN/systems/texlive/tlnet' `
    -ProfilePath "${scriptRoot}\texlive2025-win.profile"

$env:Path = [System.Environment]::ExpandEnvironmentVariables(
    [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
    [System.Environment]::GetEnvironmentVariable('Path', 'User')
)

$OldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"

try
{
    # Output info about available updates
    tlmgr update --list --all --self
}
finally
{
    $ErrorActionPreference = $OldErrorActionPreference
}
