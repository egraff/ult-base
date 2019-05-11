#!/usr/bin/env bash

# Exit on failure, verbose
set -ev

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
. ${SCRIPT_DIR}/install_texlive_linux.sh http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2017/tlnet-final ${SCRIPT_DIR}/texlive.profile
