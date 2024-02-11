#!/bin/bash
tc qdisc add dev eth0 root netem delay 100ms 20ms;
python3 ../app/udpPart/receiverKenzo3.py;