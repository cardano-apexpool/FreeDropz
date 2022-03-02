#!/bin/bash


API_HOST=<host>
API_PORT=<port>
curl -i -H "Content-Type: multipart/form-data" \
--form "airdrop_file=@airdrop.json;type=application/json" \
-X POST \
http://${API_HOST}:${API_PORT}/api/v0/submit
