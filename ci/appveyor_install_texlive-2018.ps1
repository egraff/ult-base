$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path
. "${scriptRoot}\install_texlive_windows.ps1" `
    -Repository 'http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2018/tlnet-final' `
    -ProfilePath "${scriptRoot}\..\texlive-win.profile"
