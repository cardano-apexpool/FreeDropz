#!/bin/bash


API_HOST=<host>
API_PORT=<port>
curl -i -H "Content-Type: application/json" \
--data @airdrop.json \
-X POST \
http://${API_HOST}:${API_PORT}/api/v0/submit
