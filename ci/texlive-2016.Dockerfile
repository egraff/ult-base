FROM ubuntu:bionic

RUN \
  apt-get update && \
  apt-get install -y wget apt-utils software-properties-common

RUN \
  apt-get install --no-install-recommends -y git python2.7 && \
  apt-get install --no-install-recommends -y poppler-utils ghostscript imagemagick --fix-missing && \
  apt-get install --no-install-recommends -y libfile-fcntllock-perl gcc equivs libwww-perl fontconfig unzip

COPY ci/texlive2016.profile .

RUN \
  wget http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2016/tlnet-final/install-tl-unx.tar.gz && \
  tar -xf "install-tl-unx.tar.gz" && \
  export tl_dir=$( ls | grep -P "install-tl-\d{8}$" | head -n 1 ) && \
  cd "${tl_dir}" && \
  echo "i" | ./install-tl -logfile install-tl.log -repository http://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2016/tlnet-final -profile ../texlive2016.profile && \
  export MAINTEXDIR=$(grep "TEXDIR:" "install-tl.log" | awk -F'"' '{ print $2 }') && \
  ln -s "${MAINTEXDIR}/bin"/* "/opt/texbin" && \
  sed -i 's/^PATH="/PATH="\/opt\/texbin:/' /etc/environment
