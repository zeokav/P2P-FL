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

## Repo Layout
- /src: This will contain the learning and peer-to-peer code. 
- /demo: This will contain an inference python file which will load the combined model, run it on files in /in/{nodeId}, save results in /out/{nodeId}
- /data: Each node's specific training data will be inside /data/{nodeId}