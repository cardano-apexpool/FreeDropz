from params import *


"""
network: switch between mainnet and testnet
"""
# CARDANO_NET = os.getenv('CARDANO_NET', '--mainnet')
# MAGIC_NUMBER = os.getenv('MAGIC_NUMBER', '')
CARDANO_NET = os.getenv('CARDANO_NET', '--testnet-magic')
MAGIC_NUMBER = os.getenv('MAGIC_NUMBER', '1097911063')

# addresses and spending keys
SRC_ADDRESSES = [ADDRESSES_PATH + '/payment-1.addr']
SRC_KEYS = [KEYS_PATH + '/payment-1.skey']
CHANGE_ADDRESS = ADDRESSES_PATH + '/payment-2.addr'

"""
airdrop settings
"""
TOKEN_NAME = '67bf65821e976fc17078fba603c3553aabf17e01e700c6b1bda24a62.746575746f6e'
AIRDROPS_FILE = 'airdrop.csv'
LOVELACE_AMOUNT = 1444404
ADDRESSES_PER_TRANSACTION = 120
EXTRA_LOVELACE = 3000000
SUBMITAPI_URL = 'http://<IP_OR_HOSTNAME>:8090/api/submit/tx'
