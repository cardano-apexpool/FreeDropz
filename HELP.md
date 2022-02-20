
Configuration required in config.py:

SRC_ADDRESSES = [ADDRESSES_PATH + '/dev_wallet-1.addr']
SRC_KEYS = [KEYS_PATH + '/dev_wallet-1.skey']
CHANGE_ADDRESS = ADDRESSES_PATH + '/dev_wallet-1.addr'

AIRDROPS_FILE = 'anetabtc/airdrop.csv'
AIRDROPS_FILE = 'airdrop.csv'
LOVELACE_AMOUNT = 1444404


Important variables used:
- AMOUNTS = dictionary of wallet addresses and amounts to airdrop for each wallet address
- DST_ADDRESSES = list of destination wallet addresses for the airdrop 
- spend_amounts = what we need to airdrop (sum of amounts for ADA and Tokens)
- expire = transaction expire (the slot until when the transactions are valid)
- src_addresses = list of source address, where we have the ADA and the tokens
- first_src_address = first source address, where we create the required inputs for the airdrop
- first_key = the signing key for the first source address
- change_address = address where the change will be sent
- source_transactions = list of available transactions and token_transactions (at the src_addresses)
  grouped by source address in a dictionary (source address as key)
- tokens_amounts = what we have at the SRC_ADDRESS
- transactions = the list of transactions for the airdrop (see more details below)

Next:
- create a list of required transactions (variable "transactions")
  - for each available UTxOs, add address and amounts to fill the transaction
  - if the transaction is too big (maybe 100 addresses, needs to be tested), start a new transaction
  - if the funds in the UTxO are consumed, add a new UTxO
- estimate how many UTxOs are required for the next round of transactions and 
  what amounts of ADA and tokens, if the airdrop cannot be done in one round

- create those required UTxOs

Final transactions:
- update the list of transactions: for each transaction, add the required inputs created earlier
