$ErrorActionPreference = "Stop"

# Use HTTPS for initial installer, because of flaky historic mirror (corrupted downloads in initial install step
# may cause unrecoverable errors, e.g. with error message "TeX Live [VERSION] is frozen").
# Use HTTP for subsequent install (with retries), because HTTP is too slow for CI (exceeds timeout for CI job)
$initialInstallerRepo = 'https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2022/tlnet-final'
$tlnetRepo = 'http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2022/tlnet-final'

$scriptRoot = (Resolve-Path $(If ($PSScriptRoot) { $PSScriptRoot } Else { "." })).Path
. "${scriptRoot}\install_texlive_windows.ps1" `
    -Repository $initialInstallerRepo `
    -ProfilePath "${scriptRoot}\texlive2022-win.profile"

$env:Path = [System.Environment]::ExpandEnvironmentVariables(
    [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
    [System.Environment]::GetEnvironmentVariable('Path', 'User')
)

tlmgr repository set $tlnetRepo

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
