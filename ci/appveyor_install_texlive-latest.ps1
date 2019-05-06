$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path
. .\install_texlive_windows.ps1 `
    -Repository 'http://mirrors.rit.edu/CTAN/systems/texlive/tlnet' `
    -ProfilePath "${scriptRoot}\..\texlive-win.profile"
