# FreeDropz 
A Cardano native tokens airdrop Python3 script.

## Problem to solve
The first use case for FreeDropz is to distribute a single native token type to a list of cardano addresses, without making the recipient addresses pay.
This could be used for example by a Stake Pool to distribute native tokens to its delegators, paying for the transaction fees and also an amount of ~1.45 ADA that must accompany any native token.
Using a wallet to create each individual transaction, the cost of transaction fees and amount of time spent will be very large. By combining the transactions into batches of 120 (configurable in `config.py`), the estimated transaction fees saved is about 96% (during the preliminary tests). The amount of ADA that has to be sent with the tokens cannot be avoided.

## How the script works
The ideal computer to run this script is any computer running linux.
The `cardano-cli` command will also be required, and `cardano-cli` must be able to communicate with a Cardano full node through the node socket. This can be done by running the Cardano node locally, or by connecting to a remote Cardano node's socket using `socat`. Other required commands are `jq` and `xxd`. As python requirements, only the `PyYAML` pip package will be required (see `requirements.txt`).
A cardano address, and its spending key, both stored in files on the same computer, will also be required. Ideally a new address will be generated for the airdrop, the amount of tokens and ADA required for the airdrop will be sent to this address before running the airdrop script, and after running the script, the address will never be used again (for security reasons).
The amount of tokens can be exactly the total amount required for the airdrop, but the amount of ADA must be higher, to cover the transactions fees. For 1000 addresses, probably about 1500 ADA will be required.

If the number of transactions you have to do is large (which is the purpose of this script), because of how the UTxO model works, the script will need a large amount of UTxO to use as inputs for the airdrop transactions.
For this reason, the script will actually do the airdrop in two steps:
1. The script will first analyze the airdrop file and calculate how many transactions are required for the airdrop and how many tokens and lovelace will be required for each transaction. Then it will create a transaction to create the required UTxOs at the first address configured in the `SRC_ADDRESSES` list in the `config.py` file (the details about how to configure this are below in this README).
2. After the input UTxOs are created, the airdrop transactions will be created, using these inputs.

A confirmation will be required before submitting the first transaction, and another one before submitting the airdrop transactions. Before confirming the transactions submitting, you can examine the transaction files using the following command:

    cardano-cli transaction view --tx-file transactions/tx.signed

This will display the transaction from the first step. If you changed the path where the transaction files should be stored, you also have to change the path to the `tx.signed` file in the previous command.
You can do the same with the transactions from the second step. They will have the names `tx1.signed`, `tx2.signed` and so on.

## Configuration files
Before running the script, the configuration files must be updated with your own values. There are 2 configuration files: `params.py`, which normally should not require customizations (but I recommend taking a look at the file and understanding the settings in it), and `config.py`, which require customizations.
The variables from `params.py` can also be set using environment variables with the same name.

### params.py
The settings in this file are general settings, like locations to store files (log files, transaction files), and some settings like the transaction validity time.
Example:

    TRANSACTION_EXPIRE = os.getenv('TRANSACTION_EXPIRE', 86400)

The default transaction validity time is 86400 seconds (one day). If you want to change the value, you can edit the file or you can use the environment variable `TRANSACTION_EXPIRE` by setting a different value for it. If you want to set a transaction validity of 2 hours, you can set the value 7200 for this environment variable before running the script:

    export TRANSACTION_EXPIRE=7200

All other settings in this file can be changed in ta same way.

### config.py
You will need to update the setting in the `config.py` file.
The first one is the network: select between Cardano testnet and Cardano mainnet. Before doing a real airdrop on mainnet, I recommend doing a few tests on testnet, to see and understand how the script works.
By default, testnet is selected. In order to switch to mainnet, un-comment the CARDANO_NET and MAGIC_NUMBER lines for mainnet and comment the next two lines, which are for testnet. Please note than the MAGIC_NUMBER is also important, even if it is empty, because this is how the script is testing which network is used.

    # CARDANO_NET = os.getenv('CARDANO_NET', '--mainnet')
    # MAGIC_NUMBER = os.getenv('MAGIC_NUMBER', '')
    CARDANO_NET = os.getenv('CARDANO_NET', '--testnet-magic')
    MAGIC_NUMBER = os.getenv('MAGIC_NUMBER', '1097911063')

Next, you need to configure the address (or addresses) where the ADA and the Tokens used for the airdop are. You can use one address, or you can use multiple addresses, this is why the two setting `SRC_ADDRESSES` and `SRC_KEYS` are lists (notice the `[` and `]`, which are important, to allow more than one address and one payment key).
You also need to configure the `CHANGE_ADDRESS`, where the change from the airdrop transactions will be sent. By default, the addresses and payment keys files should be saved in the `wallet` folder, but this can be changed in `params.py`.

    SRC_ADDRESSES = [ADDRESSES_PATH + '/payment-1.addr']
    SRC_KEYS = [KEYS_PATH + '/payment-1.skey']
    CHANGE_ADDRESS = ADDRESSES_PATH + '/payment-2.addr'

Next, you have to configure the tokens name in the following format (this is a testnet token used during the tests):

    TOKEN_NAME = '67bf65821e976fc17078fba603c3553aabf17e01e700c6b1bda24a62.746575746f6e'

Then you will need to set the name of the file where the airdrop list (in `csv` format) is stored, and the amount of ADA that must be sent together with the tokens. The amount of required ADA depends on the token. To find out the required amount, try to do a transaction from a normal wallet and include some tokens, and the minimum required will be displayed. For the tokens used during development, the amount is the one configured by default (in lovelace).

    AIRDROPS_FILE = 'airdrop.csv'
    LOVELACE_AMOUNT = 1444404

The airdrop file must have the following format:

    address1,amount1
    address2,amount2

The default number of addresses in one transaction will be 120. You can change it by adjusting the following variable:

    ADDRESSES_PER_TRANSACTION = 120

Setting it too high will create transaction files over the maximum transaction file and the transactions will fail. I recommend leaving it 120, the default value.

You will also need to set the amount of ADA (in lovelace, 1 ADA = 1000000 lovelace) to be used for the input UTxOs. A part of this amount will be used to cover the airdrop transaction fees, and the rest will be send to the `CHANGE_ADDRESS`. The default value is 3 ADA, but 2 ADA should also be enough. Do not set it lower than 2 ADA, otherwise the transactions might fail.

    EXTRA_LOVELACE = 3000000

The last setting is the `SUBMIT_API` url to be used for sending the transactions. The url has the following format:

    SUBMITAPI_URL = 'http://<IP address or hostname>:8090/api/submit/tx'

You will need a working submit-api for this. If the number of transactions will be big, it is better if you use a load balancer that will distribute the transactions between multiple submit-api urls.
In case you don't have a submit-api url, and you don't want to set one, you can use the local node to submit the transactions, but the preferred way is to use a submit-api url. In order to use the local node to submit the transactions, set the `SUBMITAPI_URL` value to `''` (empty string).

## Running the script
The script can be run with `python3 main.sh` or by running the `run.sh` bash script, which will set the path to the cardano-socket and execute the same command line (`python3 main.sh`). You will have to adjust the path to the cardano node socket.
There is also an example in `run.sh` of how you can use `socat` to connect to a remote node's socket.


#### Support or donations
I created this script and made it open source because I thought it might be useful for some people.
I do not expect any compensation for it. But in case someone finds it very useful and wants to support me, the best way to do it is to delegate a Cardano wallet to APEX Stake pool (ticker: `APEX`, pool ID: `538299a358e79a289c8de779f8cd09dd6a6bb286de717d1f744bb357`).
And in case someone really wants to make a donation in ADA or other Cardano native tokens, this is the address that can be used: ```addr1vy923jc5f2gck5eqzwyl8nkn4a8rc6s6w2td83egm4malns79qumx```. Thank you!
