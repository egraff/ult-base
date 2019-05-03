$ErrorActionPreference = "Stop"

cinst -y miktex

refreshenv

mpm --admin --update-db
# mpm --admin --upgrade --package-level=basic
# mpm --admin --find-updates | foreach { $_.ToString() } | select-string "^(?!miktex.*$)" > upd-packages.txt
# mpm --admin --update-some=upd-packages.txt --verbose

initexmf --admin --enable-installer --verbose
initexmf --admin --update-fndb --verbose
initexmf --admin --mkmaps --verbose
