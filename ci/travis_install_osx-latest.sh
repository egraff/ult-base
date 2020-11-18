#!/usr/bin/env bash

# Exit on failure
set -e

TLNET_REPO="http://mirrors.rit.edu/CTAN/systems/texlive/tlnet"

#brew cask install basictex
wget http://mirrors.rit.edu/CTAN/systems/mac/mactex/mactex-basictex-20200407.pkg
sudo installer -verbose -pkg ./mactex-basictex-20200407.pkg -target /

# export PATH=/Library/TeX/Distributions/.DefaultTeX/Contents/Programs/texbin:$PATH
export PATH=/Library/TeX/Distributions/Programs/texbin:$PATH

# See https://tug.org/pipermail/tex-live/2020-May/045610.html
#wget ${TLNET_REPO}/update-tlmgr-latest.sh
#sudo sh ./update-tlmgr-latest.sh

sudo tlmgr option repository ${TLNET_REPO}
#sudo -i tlmgr update --self --all
sudo -i tlmgr update --all
sudo tlmgr install            \
  collection-basic            \
  collection-bibtexextra      \
  collection-binextra         \
  collection-fontsextra       \
  collection-fontsrecommended \
  collection-fontutils        \
  collection-formatsextra     \
  collection-langenglish      \
  collection-langeuropean     \
  collection-langother        \
  collection-latex            \
  collection-latexextra       \
  collection-latexrecommended \
  collection-mathscience      \
  collection-metapost         \
  collection-pictures         \
  collection-plaingeneric     \
  collection-pstricks
