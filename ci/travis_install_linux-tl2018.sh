#!/usr/bin/env bash

# Exit on failure, verbose
set -ev

sudo apt-get update
sudo apt-get install --fix-missing
sudo apt-get install --no-install-recommends -qq poppler-utils ghostscript imagemagick --fix-missing
sudo apt-get install --no-install-recommends -qq libfile-fcntllock-perl gcc equivs libwww-perl fontconfig unzip

pdfinfo -v
compare -version
gs -v

wget http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2018/tlnet-final/install-tl-unx.tar.gz
tar -xf "install-tl-unx.tar.gz"
export tl_dir=$( ls | grep -P "install-tl-\d{8}$" | head -n 1 )

cd "${tl_dir}"
echo "i" | sudo -s ./install-tl -logfile install-tl.log -repository http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2018/tlnet-final -profile ../texlive.profile
export MAINTEXDIR=$(grep "TEXDIR:" "install-tl.log" | awk -F'"' '{ print $2 }')
sudo ln -s "${MAINTEXDIR}/bin"/* "/opt/texbin"
sudo sed -i 's/^PATH="/PATH="\/opt\/texbin:/' /etc/environment
cd ..

export PATH=/opt/texbin:$PATH
