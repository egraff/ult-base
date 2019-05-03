#!/usr/bin/env bash

# Exit on failure, verbose
set -ev

. ./install_texlive_linux.sh http://mirrors.rit.edu/CTAN/systems/texlive/tlnet

sudo -i tlmgr update --self --all
