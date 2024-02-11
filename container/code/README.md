You can develop your code here. The "code" folder will be mounted to the "/app" folder in your virtual machine.

Server IP address : 172.17.0.2

Server Interface : 172.17.0.3 dev eth0 lladdr 02:42:ac:11:00:03 STALE

Server Running : docker run -t -i --rm --privileged --cap-add=NET_ADMIN --name ceng435server -v ./code:/app:rw ceng435:latest bash

Client IP address : 172.17.0.3

Client Interface : 172.17.0.2 dev eth0 lladdr 02:42:ac:11:00:02 REACHABLE

Client Running : docker run -t -i --rm --privileged --cap-add=NET_ADMIN --name ceng435client -v ./code:/app:rw ceng435:latest bash

