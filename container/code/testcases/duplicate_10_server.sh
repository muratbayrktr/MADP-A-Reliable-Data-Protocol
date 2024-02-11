#!/bin/bash
tc qdisc add dev eth0 root netem duplicate 10%;
python3 ../app/udpPart/senderKenzo3.py;