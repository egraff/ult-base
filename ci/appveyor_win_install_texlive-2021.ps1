$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path
. "${scriptRoot}\install_texlive_windows.ps1" `
    -Repository 'https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2021/tlnet-final' `
    -ProfilePath "${scriptRoot}\texlive2021-win.profile"
