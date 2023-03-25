$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path
. "${scriptRoot}\install_texlive_windows.ps1" `
    -Repository 'https://mirrors.rit.edu/CTAN/systems/texlive/tlnet' `
    -ProfilePath "${scriptRoot}\texlive2022-win.profile"
