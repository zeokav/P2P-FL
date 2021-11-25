#!/bin/bash

echo "Building image..."
sudo docker build . -t p2p-fl

ports=( 6000 6001 6002 6003 6004 )

echo "Configuring IP table..."
for port in "${ports[@]}" ; do
    sudo iptables -A INPUT -p tcp --dport ${port} -j ACCEPT
    echo "Opened port ${port}!"
done

sudo docker-compose up

echo "Restoring IP table state..."
for port in "${ports[@]}" ; do
    sudo iptables -D INPUT -p tcp --dport ${port} -j ACCEPT
    echo "Closed port ${port}!"
done
