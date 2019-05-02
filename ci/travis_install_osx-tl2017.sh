#!/usr/bin/env bash

# Exit on failure
set -e

wget http://ftp.math.utah.edu/pub/tex/historic/systems/mactex/2017/mactex-basictex-20170607.pkg
sudo installer -verbose -pkg ./mactex-basictex-20170607.pkg -target /

# export PATH=/Library/TeX/Distributions/.DefaultTeX/Contents/Programs/texbin:$PATH
export PATH=/Library/TeX/Distributions/Programs/texbin:$PATH

sudo tlmgr option repository http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2017/tlnet-final
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
