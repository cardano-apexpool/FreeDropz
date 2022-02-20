import os
env = dict(os.environ)


# the folder where the addresses files and spending key files are stored
KEYS_PATH = os.getenv('KEYS_PATH', 'wallet')
ADDRESSES_PATH = os.getenv('ADDRESSES_PATH', 'wallet')
# the folder where the log files are stored
FILES_PATH = os.getenv('FILES_PATH', 'files')
LOG_FILE = os.getenv('LOG_FILE', FILES_PATH + '/application.log')
TRANSACTIONS_LOG_FILE = os.getenv('TRANSACTIONS_LOG_FILE', FILES_PATH + '/transactions.log')
# the folder where the transaction files are stored
TRANSACTIONS_PATH = os.getenv('TRANSACTIONS_PATH', 'transactions')
# protocol parameters file
PROTOCOL_FILE = os.getenv('PROTOCOL_FILE', FILES_PATH + '/protocol-parameters.json')
# default transaction validity time
TRANSACTION_EXPIRE = os.getenv('TRANSACTION_EXPIRE', 86400)
# max numbers of UTxOs to use in a transaction
MAX_IN_UTXOS = os.getenv('MAX_IN_UTXOS', 250)
# sleep timeout during various steps of the script
SLEEP_TIMEOUT = os.getenv('SLEEP_TIMEOUT', 5)
