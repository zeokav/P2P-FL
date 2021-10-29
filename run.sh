echo "Building image..."
sudo docker build . -t p2p-fl

echo "Configuring IP table..."
for port in {6000..6004} ; do
    sudo iptables -A INPUT -p tcp --dport ${port} -j ACCEPT
    echo "Opened port ${port}!"
done

sudo docker-compose up

echo "Restoring IP table state..."
for port in {6000..6004} ; do
    sudo iptables -D INPUT -p tcp --dport ${port} -j ACCEPT
    echo "Closed port ${port}!"
done