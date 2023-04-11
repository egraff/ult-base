FROM ubuntu:focal

RUN \
  apt-get update && \
  export DEBIAN_FRONTEND=noninteractive && \
  apt-get install --no-install-recommends -y wget apt-utils software-properties-common

RUN \
  export DEBIAN_FRONTEND=noninteractive && \
  apt-get install --no-install-recommends -qq -y git python3 curl && \
  apt-get install --no-install-recommends -qq -y poppler-utils ghostscript imagemagick --fix-missing && \
  apt-get install --no-install-recommends -qq -y libfile-fcntllock-perl gcc equivs libwww-perl fontconfig && \
  apt-get install --no-install-recommends -qq -y unzip openssh-client rsync

# Install .NET 3.1 runtime, required by secure-file utility
RUN \
  export DEBIAN_FRONTEND=noninteractive && \
  wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb && \
  dpkg -i packages-microsoft-prod.deb && \
  rm packages-microsoft-prod.deb && \
  apt-get update && \
  apt-get install --no-install-recommends -y dotnet-runtime-3.1

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
