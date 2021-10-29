FROM python:3.9.7

# Setting up the python environment
COPY requirements.txt /home/requirements.txt
RUN pip3 install -r /home/requirements.txt

# For training data and inference i/o
RUN mkdir -p /home/data && mkdir /home/demo

# For the peer to peer code
RUN mkdir -p /home/work
COPY /src /home/work
WORKDIR /home/work

# Set up entrypoint and run
COPY ./entrypoint.sh /home/entrypoint.sh
RUN chmod +x /home/entrypoint.sh
ENTRYPOINT /home/entrypoint.sh