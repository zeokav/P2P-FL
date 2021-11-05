# P2P Federated learning

## Overview
The plan is to run a number of "peers" on one system, and integrate learning with peers on other systems.  

## Development Setup
For development, make sure you're not using the global python. To create a virtual environment, run:`python3 -m venv venv`

Once you have this, you can load the project up in any IDE and choose this directory for the interpreter binary.

When you're working, always switch to this environment: `source ./venv/bin/activate`

## Adding/Restoring Deps For Easier Local Dev
Before you start developing, after switching into the virtual environment, please run `pip3 install -r requirements.txt` to install any dependencies required. 

If you end up adding any deps when developing locally, make sure to save it before creating the docker containers: `pip3 freeze > requirements.txt` 

## Running
Execute `./run.sh`. This will:
- Build the image, and setup the python env inside the image.
- Create entries in the IP table to interface with the created containers.
- Run the image as 5 different containers and these will be externally visible.

#Accessing the Docker
Once the docker is created, follow these steps to access any container in the docker.
- sudo docker container ls - lists the containers with their ids in the docker
- sudo docker exec -it container_id bash
You will have access to the container now. The source code is present in /home/work.

Running Centralized Federated Learning Example (single docker node)- 

Run server
Go to home/work/p2plib/cmd/flat directory
python3 fl_server.py 127.0.0.1 9004

Run client 1
Open a new terminal and access the same docker using sudo docker exec -it container_id bash (make sure you give the same container_id as the server)
Go to home/work/p2plib/cmd/flat directory
python3 fl_client.py 127.0.0.1 9005 127.0.0.1:9004

Run client 2
Open a new terminal and access the same docker using sudo docker exec -it container_id bash (make sure you give the same container_id as the server and client1)
Go to home/work/p2plib/cmd/flat directory
python3 fl_client.py 127.0.0.1 9006 127.0.0.1:9004

## Repo Layout
- /src: This will contain the learning and peer-to-peer code. 
- /demo: This will contain an inference python file which will load the combined model, run it on files in /in/{nodeId}, save results in /out/{nodeId}
- /data: Each node's specific training data will be inside /data/{nodeId}
