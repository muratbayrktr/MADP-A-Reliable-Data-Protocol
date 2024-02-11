#!/bin/bash
tc qdisc add dev eth0 root netem loss 0%;
python3 ../app/udpPart/senderKenzo3.py;