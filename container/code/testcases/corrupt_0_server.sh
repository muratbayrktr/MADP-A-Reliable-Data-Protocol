#!/bin/bash
tc qdisc add dev eth0 root netem corrupt 0%;
python3 ../app/udpPart/senderKenzo3.py;