# P2P Federated learning with multi-tiered architecture

## Overview
The plan is to run a number of "peers" on one system, train them individually and share knowledge across the swarm of containers.
We explore the performance of such a system with different peer configurations.

## Deliverables
We work on top of the p2plib shared by [James Bae](https://github.com/theued) to create a peer-to-peer aware application (currently closed-source). 
- Demo UI code in demo/
- Demo server code in src/server.py
- Application code in src/p2plib/cmd/flat/fl_peer.py (along with changes in flat.go)
- Evaluation docker environment set up using the dockerfile and docker-compose.yaml
- PPT in ./Group11.FinalReport.pptx

## Running the code
### To quickly bring up an environment and run the code on docker
Execute `./run.sh`. This will:
- Build the image, and setup the python env inside the image.
- Create a docker-internal network for communication across nodes. Also volume mount required dirs on the containers. 
- Run the image as 6 different containers (acting as 6 peers) joining the same network incrementally.
- Start the container with fl_peer.py running at startup. Other peers will discover any container that joins in.
- Run the flask server for interaction on one of the nodes. 

### To run on bare metal
First the python environment must be set up. To do this, go to the /pre folder. Run the two shell files:
```shell
cd pre
sudo sh install_fl.sh
sudo sh install_go.sh
```
Repeat the same process in other machines where you'd want to launch peers. 

Note down the IP address on your machine using `ifconfig`.
You can then start up a peer by running (and start an interface server):
```shell
cd src/p2plib/cmd/flat

# Start server in the background
python3 ../../../server.py &

# Start peer
python3 fl_peer.py <SELF_IP> <PORT>
```

To run more peers, enter those machines and start. Bootstrap IP and port are processes you have spun up before in other systems:
```shell
cd src/p2plib/cmd/flat
python3 fl_peer.py <SELF_IP> <PORT> <BOOTSTRAP_IP:PORT>
```

You can view the visualization by running the UI locally
```shell
cd demo

# Install dependencies
npm i

npm start

# Go to src/app/nodeviz/*.ts, change the IP address there to the machine where the 
# flask server is running. 

# Navigate to localhost:4200 in chrome
```


## Accessing the Docker container
Once the container is created, follow these steps to access any container in the docker.
- sudo docker container ls - lists the containers with their ids in the docker
- sudo docker exec -it <container_id> bash
You will have access to the container now. The source code is present in /home/work.

# External open source code and other tools used 
- For testing scalability, we brought up instances in AWS: https://aws.amazon.com/
- For spinning up the environment for development, we rely on docker: https://www.docker.com/
- All model training and evaluation is done using the tensorflow library (using Keras abstraction): https://www.tensorflow.org/
- Dataset used for evaluation is CIFAR-10: https://www.cs.toronto.edu/~kriz/cifar.html
- For the demo, we wrote the UI in angular (https://angular.io/) and the backend using Flask (https://flask.palletsprojects.com/en/2.0.x/)
- The application layer for the p2p nodes was written in Python (https://www.python.org/)