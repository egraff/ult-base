$ErrorActionPreference = "Stop"

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path
. "${scriptRoot}\install_texlive_windows.ps1" `
    -Repository 'http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2021/tlnet-final' `
    -ProfilePath "${scriptRoot}\texlive2021-win.profile"

$env:Path = [System.Environment]::ExpandEnvironmentVariables(
    [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
    [System.Environment]::GetEnvironmentVariable('Path', 'User')
)

while ($true)
{
    tlmgr install `
        collection-basic `
        collection-bibtexextra `
        collection-binextra `
        collection-fontsextra `
        collection-fontsrecommended `
        collection-fontutils `
        collection-formatsextra `
        collection-langenglish `
        collection-langeuropean `
        collection-langother `
        collection-latex `
        collection-latexextra `
        collection-latexrecommended `
        collection-mathscience `
        collection-metapost `
        collection-pictures `
        collection-plaingeneric `
        collection-pstricks `
        collection-wintools

    if ($?)
    {
        break
    }
}

tlmgr path add
