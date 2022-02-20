#!/bin/bash


########################################################################################################################################################
# socat example                                                                                                                                        #
# on the cardano node:                                                                                                                                 #
# socat TCP-LISTEN:3005,reuseaddr,fork UNIX-connect:/home/cardano/cardano-node/db/node.socket                                                          #
# on the computer where the script will run                                                                                                            #
# socat UNIX-LISTEN:/run/cardano-node.socket,fork,reuseaddr,unlink-early,user=cardano,group=cardano,mode=755 TCP:<IP ADDRESS OF THE CARDANO NODE>:3005 #
########################################################################################################################################################

CARDANO_NODE_SOCKET_PATH=/run/cardano-node-testnet.socket python3 main.py
