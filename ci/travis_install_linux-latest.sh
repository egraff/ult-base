#!/usr/bin/env bash

# Exit on failure, verbose
set -ev

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
. ${SCRIPT_DIR}/install_texlive_linux.sh http://mirrors.rit.edu/CTAN/systems/texlive/tlnet ${SCRIPT_DIR}/texlive.profile

sudo -i tlmgr update --self --all
