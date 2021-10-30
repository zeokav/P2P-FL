FROM python:3.9.7

# Setting up the python environment
COPY requirements.txt /home/requirements.txt
RUN pip3 install -r /home/requirements.txt

# Pre-install libraries for p2plib
COPY /pre /home/pre
RUN sh /home/pre/install_fl.sh && sh /home/pre/install_go.sh

# For training data and inference i/o
RUN mkdir -p /home/data && mkdir /home/demo

# For the peer to peer code
RUN mkdir -p /home/work
COPY /src /home/work

# Set up entrypoint and run
WORKDIR /home/work
COPY ./entrypoint.sh /home/entrypoint.sh
RUN chmod +x /home/entrypoint.sh
ENTRYPOINT /home/entrypoint.sh
