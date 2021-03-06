#!/usr/bin/env bash

# Exit on failure
set -e

TLNET_REPO="http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2018/tlnet-final"

wget http://ftp.math.utah.edu/pub/tex/historic/systems/mactex/2018/mactex-basictex-20180417.pkg
sudo installer -verbose -pkg ./mactex-basictex-20180417.pkg -target /

# export PATH=/Library/TeX/Distributions/.DefaultTeX/Contents/Programs/texbin:$PATH
export PATH=/Library/TeX/Distributions/Programs/texbin:$PATH

# See https://tug.org/pipermail/tex-live/2020-May/045610.html
wget ${TLNET_REPO}/update-tlmgr-latest.sh
sudo sh ./update-tlmgr-latest.sh

sudo tlmgr option repository ${TLNET_REPO}
sudo -i tlmgr update --self --all
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
