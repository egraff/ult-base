FROM ubuntu:bionic

RUN \
  apt-get update

RUN \
  apt-get install --no-install-recommends -y poppler-utils ghostscript imagemagick --fix-missing && \
  apt-get install --no-install-recommends -y libfile-fcntllock-perl gcc equivs libwww-perl fontconfig unzip

COPY ci/texlive.profile .

RUN \
  wget http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2017/tlnet-final/install-tl-unx.tar.gz && \
  tar -xf "install-tl-unx.tar.gz" && \
  export tl_dir=$( ls | grep -P "install-tl-\d{8}$" | head -n 1 ) && \
  cd "${tl_dir}" && \
  echo "i" | sudo -s ./install-tl -logfile install-tl.log -repository http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2017/tlnet-final -profile ../texlive.profile && \
  export MAINTEXDIR=$(grep "TEXDIR:" "install-tl.log" | awk -F'"' '{ print $2 }') && \
  sudo ln -s "${MAINTEXDIR}/bin"/* "/opt/texbin" && \
  sudo sed -i 's/^PATH="/PATH="\/opt\/texbin:/' /etc/environment
