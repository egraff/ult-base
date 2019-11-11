# escape=`

FROM cirrusci/windowsservercore:2019

RUN cinst -y python2
RUN cinst -y msys2 --params "/InstallDir:C:\msys64"

RUN powershell.exe -Command `
  $ErrorActionPreference = 'Stop'; `
  Start-Process cinst -ArgumentList '-y imagemagick -PackageParameters LegacySupport=true' -Wait ; `
  Start-Process cinst -ArgumentList '-y ghostscript' -Wait ; `
  Start-Process cinst -ArgumentList '-y xpdf-utils
