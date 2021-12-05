 apt-get update
 apt-get -y install aptitude
 apt-get install -y software-properties-common
 add-apt-repository -y ppa:openjdk-r/ppa
# add-apt-repository ppa:webupd8team/java -y
 add-apt-repository -y ppa:ubuntu-toolchain-r/test
 add-apt-repository -y ppa:george-edison55/cmake-3.x
 add-apt-repository -y ppa:deadsnakes/ppa
 apt-get update

apt-get install  -y libcurl4-openssl-dev
apt-get install -y curl
apt-get install -y wget
#apt-get install -y gcc g++ build-essential libopenmpi-dev openmpi-bin default-jdk cmake zlib1g-dev
apt-get install -y gcc build-essential cmake
apt-get install -y gcc-4.9 g++-4.9
apt-get install -y python-minimal
apt-get install -y vim
apt-get install -y git-core
apt-get install -y ant

apt install -y openjdk-8-jdk
#apt-get install -y openjdk-8-jdk
#apt install oracle-java8-set-default

#ML
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64/jre
apt-get install -y python3.6
rm /usr/bin/python3
ln -s /usr/bin/python3.6 /usr/bin/python3

update-alternatives --install /usr/bin/cmake cmake /usr/local/bin/cmake 1 --force

apt-get install -y python-pip --upgrade
apt-get install -y python3-pip --upgrade
apt-get install -y python-dev
apt-get install -y python3-dev
apt-get install -y gawk
apt-get install -y python-virtualenv swig python-wheel libcurl3-dev libssl-dev libffi-dev libxml2-dev libxslt1-dev zlib1g-dev

wget https://bootstrap.pypa.io/ez_setup.py -O - | python3

#virtualenv --system-site-packages -p python3 ./venv
#source ./venv/bin/activate  # sh, bash, ksh, or zsh
pip3 install --upgrade pip
pip3 install keras
pip3 install --upgrade tensorflow requests --ignore-installed
pip3 install torch
pip3 install torchvision
pip3 install numpy
pip3 install pandas
pip3 install scikit-learn
pip3 install msgpack-python
pip3 install msgpack_numpy
pip3 install flask
pip3 install flask_socketio
pip3 install -U socketIO-client --user
pip3 install opencv-python

pip3 install Flask-SocketIO==4.3.1
pip3 install python-engineio==3.13.2
pip3 install python-socketio==4.6.0

apt-get -y install g++ gfortran
apt-get -y install git pkg-config
apt-get -y autoremove
rm -rf /var/lib/apt/lists/*

cd ~
chmod -R 777 .local

#wget https://repo.anaconda.com/archive/Anaconda3-5.3.1-Linux-x86_64.sh
#bash Anaconda3-5.3.1-Linux-x86_64.sh

#git clone https://github.com/tensorflow/tensorflow.git
#git clone --recursive https://github.com/pytorch/pytorch
#pip install pyyaml
#pip install typing
#cd pytorch

#cmake latest
#wget http://www.cmake.org/files/v3.10/cmake-3.10.1.tar.gz 
#tar -xvzf cmake-3.10.1.tar.gz 
#cd cmake-3.10.1/
#./configure
#make
#make install

#wget http://ftp.gnu.org/gnu/glibc/glibc-2.23.tar.gz
#tar zxvf glibc-2.23.tar.gz
#cd glibc-2.23
#mkdir build
#cd build
#../configure --prefix=/opt/glibc-2.23
#make
#make install

# for old ubuntu 14.04
#wget http://www.mellanox.com/downloads/ofed/MLNX_OFED-3.1-1.0.3/MLNX_OFED_LINUX-3.1-1.0.3-ubuntu14.04-x86_64.tgz .
#tar -xvf MLNX_OFED_LINUX-3.1-1.0.3-ubuntu14.04-x86_64.tgz
#cd ~/MLNX_OFED_LINUX-3.1-1.0.3-ubuntu14.04-x86_64
#./mlnxofedinstall --add-kernel-support --without-fw-update --force

#apt-get remove -y mlnx-ofed-kernel-dkms mlnx-ofed-kernel-utils ofed-scripts kernel-mft-dkms mstflint knem knem-dkms iser-dkms

#cd ~/MLNX_OFED_LINUX-3.1-1.0.3-ubuntu14.04-x86_64
#./mlnxofedinstall --add-kernel-support --without-fw-update --force

#ofed_info | head -1


