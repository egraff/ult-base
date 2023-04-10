FROM ubuntu:bionic

RUN \
  apt-get update && \
  apt-get install -y wget apt-utils software-properties-common

RUN \
  apt-get install --no-install-recommends -y git python3 curl && \
  apt-get install --no-install-recommends -y poppler-utils ghostscript imagemagick --fix-missing && \
  apt-get install --no-install-recommends -y libfile-fcntllock-perl gcc equivs libwww-perl fontconfig unzip

COPY ci/texlive2023.profile ./texlive.profile

RUN \
  export TLNET_REPO=http://mirrors.rit.edu/CTAN/systems/texlive/tlnet && \
  wget ${TLNET_REPO}/install-tl-unx.tar.gz && \
  tar -xf "install-tl-unx.tar.gz"

RUN \
  export TLNET_REPO=http://mirrors.rit.edu/CTAN/systems/texlive/tlnet && \
  export tl_dir=$( ls | grep -P "install-tl-\d{8}$" | head -n 1 ) && \
  ${tl_dir}/install-tl -no-gui -logfile install-tl.log -repository ${TLNET_REPO} -profile ./texlive.profile
  
RUN \
  export MAINTEXDIR=$(grep "TEXDIR:" "install-tl.log" | awk -F'"' '{ print $2 }') && \
  ln -s "${MAINTEXDIR}/bin"/* "/opt/texbin" && \
  sed -i 's/^PATH="/PATH="\/opt\/texbin:/' /etc/environment && \
  rm -rf ${tl_dir} "install-tl-unx.tar.gz"
