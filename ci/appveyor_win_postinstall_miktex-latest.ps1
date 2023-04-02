$ErrorActionPreference = "Stop"

initexmf --admin --update-fndb --verbose

# Hack to try and work around problem auto-installing currfile
miktex --admin --verbose packages install currfile
