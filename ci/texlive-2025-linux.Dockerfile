FROM ubuntu:noble

RUN \
  apt-get update && \
  export DEBIAN_FRONTEND=noninteractive && \
  apt-get install --no-install-recommends -y wget apt-utils software-properties-common ca-certificates

RUN \
  export DEBIAN_FRONTEND=noninteractive && \
  apt-get install --no-install-recommends -qq -y git python3 python3-pycryptodome curl patch && \
  apt-get install --no-install-recommends -qq -y poppler-utils ghostscript imagemagick --fix-missing && \
  apt-get install --no-install-recommends -qq -y libfile-fcntllock-perl libwww-perl liblwp-protocol-https-perl && \
  apt-get install --no-install-recommends -qq -y gcc equivs fontconfig && \
  apt-get install --no-install-recommends -qq -y unzip openssh-client rsync

COPY ci/texlive2024.profile ./texlive.profile

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
