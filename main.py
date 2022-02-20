#!/usr/bin/env python3


import json
import requests
import logging.handlers
from time import sleep
from library import *


if __name__ == '__main__':

    """
    create some required folders to store log and transaction file
    """
    try:
        if not os.path.exists(FILES_PATH):
            os.mkdir(FILES_PATH)
        if not os.path.exists(TRANSACTIONS_PATH):
            os.mkdir(TRANSACTIONS_PATH)
    except Exception as e:
        print('Error creating the required folders: %s' % e)
        sys.exit(1)
    """
    Set up logging
    """
    handler = logging.handlers.WatchedFileHandler(LOG_FILE)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    applog = logging.getLogger('airdrops')
    applog.addHandler(handler)
    applog.setLevel(logging.INFO)

    applog.info("*****************************************************************")
    applog.info('Starting')

    """
    read the input data file to see how much ADA and how many tokens are required.
    """
    airdrops_list = []
    try:
        with open(AIRDROPS_FILE, 'r') as f:
            airdrops_file = f.read()
    except Exception as e:
        print('Error opening the airdrops file: %s' % e)
        applog.exception('Error opening the airdrops file: %s' % e)
        sys.exit(1)
    for line in airdrops_file.splitlines():
        wallet = line.split(',')
        item = {}
        item['address'] = wallet[0]
        item['tokens_amount'] = wallet[1]
        airdrops_list.append(item)

    """
    DST_ADDRESSES = list of destination wallet addresses for the airdrop 
    AMOUNTS = dictionary of wallet addresses and amounts to airdrop for each wallet address
    """
    DST_ADDRESSES = []
    AMOUNTS = {}
    total_lovelace = 0
    total_tokens = 0
    for item in airdrops_list:
        # read the values from the airdrops_list
        address = item['address']
        t_amount = int(item['tokens_amount'])
        # create the dictionary with the final airdrops list
        amount = []
        lovelace_amount = {}
        tokens_amount = {}
        lovelace_amount['token'] = 'lovelace'
        lovelace_amount['amount'] = LOVELACE_AMOUNT
        tokens_amount['token'] = TOKEN_NAME
        tokens_amount['amount'] = t_amount
        amount.append(lovelace_amount)
        amount.append(tokens_amount)
        total_lovelace += LOVELACE_AMOUNT
        total_tokens += int(t_amount)
        AMOUNTS[address] = amount
        DST_ADDRESSES.append(address)
    print('Airdrop information from the airdrops file:')
    print('%d airdrops' % len(airdrops_list))
    print('total lovelace: %d' % total_lovelace)
    print('total tokens: %d\n' % total_tokens)
    applog.info('Airdrop information from the airdrops file:')
    applog.info('%d airdrops' % len(airdrops_list))
    applog.info('total lovelace: %d' % total_lovelace)
    applog.info('total tokens: %d' % total_tokens)
    spend_amounts = {}
    spend_amounts['lovelace'] = total_lovelace
    spend_amounts[TOKEN_NAME] = total_tokens

    # generate the protocol file
    if len(MAGIC_NUMBER) == 0:
        cmd = ["cardano-cli", "query", "protocol-parameters", CARDANO_NET, "--out-file", PROTOCOL_FILE]
    else:
        cmd = ["cardano-cli", "query", "protocol-parameters", CARDANO_NET, str(MAGIC_NUMBER),
               "--out-file", PROTOCOL_FILE]
    _, _ = cardano_cli_cmd(cmd)

    # query tip
    if len(MAGIC_NUMBER) == 0:
        cmd = ["cardano-cli", "query", "tip", CARDANO_NET]
    else:
        cmd = ["cardano-cli", "query", "tip", CARDANO_NET, str(MAGIC_NUMBER)]
    out, err = cardano_cli_cmd(cmd)

    # set transaction expire time in TRANSACTION_EXPIRE seconds (default 86400 = 1 day)
    expire = json.loads(out)['slot'] + TRANSACTION_EXPIRE

    # read the keys and the addresses (where the tokens and lovelace are) from the files
    try:
        first_key = SRC_KEYS[0]
    except Exception as err:
        print('Error reading SRC_KEYS %s: %s' % (SRC_KEYS, err))
        applog.exception('Error reading SRC_KEYS %s: %s' % (SRC_KEYS, err))
        sys.exit(1)

    src_addresses = []
    first_src_address = ''
    for address_file in SRC_ADDRESSES:
        try:
            with open(address_file, 'r') as f:
                src_addr = f.read()
                src_addresses.append(src_addr)
                if len(src_addresses) == 1:
                    first_src_address = src_addr
        except Exception as err:
            print('Error while opening the file %s: %s' % (address_file, err))
            applog.exception('Error while opening the file %s: %s' % (address_file, err))
            sys.exit(1)
    # read the change address from the file
    change_address = ''
    try:
        with open(CHANGE_ADDRESS, 'r') as f:
            change_address = f.read()
    except Exception as err:
        print('Error while opening the file %s: %s' % (CHANGE_ADDRESS, err))
        applog.exception('Error while opening the file %s: %s' % (CHANGE_ADDRESS, err))
        sys.exit(1)

    # source UTxOs grouped by source address
    source_transactions = {}
    # get the list of transactions from all source addresses
    src_transactions = []
    src_token_transactions = []
    tokens_amounts = []
    for src_addr in src_addresses:
        src_trans, src_token_trans, tok_amounts, out, err = get_transactions(src_addr)
        if err:
            print(err)
            applog.error(err)
            sys.exit(1)
        else:
            applog.info('*******************************************')
            applog.info(src_token_trans)
            applog.info('*******************************************')
            utxos = {}
            utxos['src_transactions'] = src_trans
            utxos['src_token_transactions'] = src_token_trans
            source_transactions[src_addr] = utxos
            applog.info('%d src_transactions and %d src_token_transactions available at the address %s' %
                  (len(src_trans), len(src_token_trans), src_addr))
            src_transactions += src_trans
            src_token_transactions += src_token_trans
            tokens_amounts.append(tok_amounts)
    #
    total_available = {}
    for t in tokens_amounts:
        for k in t.keys():
            if k in total_available:
                total_available[k] += t[k]
            else:
                total_available[k] = t[k]
    tokens_amounts = total_available
    # debug
    if len(src_transactions) == 0 and len(src_token_transactions) == 0:
        print('No source transactions (UTXOs)!')
        sys.exit(1)
    print('Amounts available: %s' % tokens_amounts)
    print('Amounts to spend: %s' % spend_amounts)
    applog.info('Source transactions: %s' % src_transactions)
    applog.info('Source token transactions: %s' % src_token_transactions)
    applog.info('Amounts available: %s' % tokens_amounts)
    applog.info('Amounts to spend: %s' % spend_amounts)

    # validate transaction
    if not validate_transaction(spend_amounts, tokens_amounts):
        print('Spending more than existing amounts is not possible!')
        applog.error('Spending more than existing amounts is not possible!')
        sys.exit(1)
    else:
        extra_ada = int(len(airdrops_list) / ADDRESSES_PER_TRANSACTION * (860000 + EXTRA_LOVELACE) / 1000000 + 1)
        print('Transaction is possible - available amounts are more than the amounts to spend.')
        if spend_amounts['lovelace'] + extra_ada * 1000000 > tokens_amounts['lovelace']:
            print('Please be sure there are about %d extra ADA in the source address.\n' % extra_ada)

    applog.info('source_transactions: %s\n' % source_transactions)

    """
    Create the airdrop transactions list in memory
    """
    transactions = []
    transaction = {}
    inputs = []
    outputs = []
    change_address = src_addr
    trans_lovelace = 0
    trans_tokens = 0
    count = 0
    # for the totals of all transactions
    amount_lovelace = 0
    amount_tokens = 0
    for address in DST_ADDRESSES:
        count += 1
        output = {}
        output['address'] = address
        output['lovelace'] = AMOUNTS[address][0]['amount']
        output[TOKEN_NAME] = AMOUNTS[address][1]['amount']
        # calculate the total amount of ADA and Tokens in this transaction
        trans_lovelace += output['lovelace']
        trans_tokens += output[TOKEN_NAME]
        # update the total amount of ADA and Tokens in all transactions
        amount_lovelace += output['lovelace']
        amount_tokens += output[TOKEN_NAME]
        outputs.append(output)
        if count >= ADDRESSES_PER_TRANSACTION:
            # total amounts for this transaction
            total_amounts = {}
            total_amounts['lovelace'] = trans_lovelace
            total_amounts[TOKEN_NAME] = trans_tokens
            # create the transaction and append it to the transactions list
            transaction['inputs'] = inputs
            transaction['outputs'] = outputs
            transaction['change_address'] = change_address
            transaction['total_amounts'] = total_amounts
            transactions.append(transaction)
            # re-initialize the variables for the next iteration
            transaction = {}
            inputs = []
            outputs = []
            trans_lovelace = 0
            trans_tokens = 0
            count = 0
    # last transaction, which has less than the max number of outputs
    if count > 0:
        # total amounts for this transaction
        total_amounts = {}
        total_amounts['lovelace'] = trans_lovelace
        total_amounts[TOKEN_NAME] = trans_tokens
        # create the transaction and append it to the transactions list
        transaction['inputs'] = inputs
        transaction['outputs'] = outputs
        transaction['change_address'] = change_address
        transaction['total_amounts'] = total_amounts
        transactions.append(transaction)

    print('Number of transactions to do: %d' % len(transactions))
    applog.debug('Transactions list:')
    t_cnt = 0
    for t in transactions:
        t_cnt += 1
        applog.debug('Transaction %d: %s' % (t_cnt, t))
    # debug
    print('total lovelace in transactions: %d' % amount_lovelace)
    print('total tokens in transactions: %d' % amount_tokens)
    applog.info('total lovelace: %d' % amount_lovelace)
    applog.info('total tokens: %d' % amount_tokens)

    """
    Create the initial transaction, which will create the UTxOs to the airdrop transactions
    """
    transaction = {}
    cmd = ['cardano-cli', 'transaction', 'build']
    # add the inputs
    for t in src_transactions:
        cmd.append('--tx-in')
        cmd.append(t['hash'] + '#' + t['id'])
    for t in src_token_transactions:
        cmd.append('--tx-in')
        cmd.append(t['hash'] + '#' + t['id'])
    for t in transactions:
        cmd.append('--tx-out')
        cmd.append(first_src_address + '+' + str(t['total_amounts']['lovelace'] + EXTRA_LOVELACE) + '+' +
                   str(t['total_amounts'][TOKEN_NAME]) + ' ' + TOKEN_NAME + '')
    for t in src_token_transactions:
        for am in t['amounts']:
            if am['token'] != TOKEN_NAME and am['token'] != 'lovelace':
                cmd.append('--tx-out')
                cmd.append(first_src_address + '+2000000+' + str(am['amount']) + ' ' + str(am['token']) + '')
    cmd.append('--tx-out')
    cmd.append(first_src_address + '+2000000+' + str(tokens_amounts[TOKEN_NAME] - spend_amounts[TOKEN_NAME])
               + ' ' + str(TOKEN_NAME) + '')
    cmd.append('--change-address')
    cmd.append(change_address)
    cmd.append('--invalid-hereafter')
    cmd.append(str(expire))
    cmd.append('--out-file')
    cmd.append(TRANSACTIONS_PATH + '/tx.raw')
    cmd.append(CARDANO_NET)
    if len(MAGIC_NUMBER) != 0:
        cmd.append(str(MAGIC_NUMBER))
    out, err = cardano_cli_cmd(cmd)
    if err:
        print(err)
        sys.exit(1)
    print(out.strip())
    applog.info(out)

    # sign transaction
    _, err = sign_transaction(SRC_KEYS, TRANSACTIONS_PATH + '/tx.raw', TRANSACTIONS_PATH + '/tx.signed')
    if err:
        print(err)
        sys.exit(1)

    # get the transaction id
    cmd = ["cardano-cli", "transaction", "txid", "--tx-file", TRANSACTIONS_PATH + '/tx.signed']
    # execute the command
    out, err = cardano_cli_cmd(cmd)
    if err:
        print(err)
        sys.exit(1)
    TXID = out.strip()
    print('Transaction ID: %s' % TXID)
    applog.info('Transaction ID: %s' % TXID)

    # encode transactions in cbor format
    cmd = 'jq .cborHex ' + TRANSACTIONS_PATH + '/tx.signed | xxd -r -p > ' + TRANSACTIONS_PATH + '/tx.signed.cbor'
    stream = os.popen(cmd)
    out = stream.read().strip()
    print(out)

    # list the transaction file on disk, to see that everything is fine
    # and that the size is ok (less than the maximum transaction size of 16 KB)
    cmd = 'ls -l ' + TRANSACTIONS_PATH + '/tx.signed.cbor'
    stream = os.popen(cmd)
    out = stream.read().strip()
    print(out)

    # ask for confirmation before sending the transaction
    while True:
        reply = input('Confirm? [y/n] ')
        if reply.lower() in ('y', 'yes'):
            if SUBMITAPI_URL == '':
                # submit transaction to the local node
                if len(MAGIC_NUMBER) == 0:
                    cmd = ["cardano-cli", "transaction", "submit", "--tx-file", TRANSACTIONS_PATH + '/tx.signed',
                           CARDANO_NET]
                else:
                    cmd = ["cardano-cli", "transaction", "submit", "--tx-file", TRANSACTIONS_PATH + '/tx.signed',
                           CARDANO_NET,
                           str(MAGIC_NUMBER)]
                out, err = cardano_cli_cmd(cmd)
                if err:
                    print(err)
                    sys.exit(1)
                print('Transaction executed')
                print(out)
                applog.info(out)
            else:
                try:
                    # read transaction from file
                    with open(TRANSACTIONS_PATH + '/tx.signed.cbor', 'rb') as f:
                        data = f.read()
                    # submit the transaction to the submit-api url
                    headers = {'Accept': '*/*', 'Content-Type': 'application/cbor'}
                    response = requests.post(SUBMITAPI_URL, data=data, headers=headers)
                    applog.info(response.text + ' submitted')
                    print(str(response.status_code) + ' ' + response.text + ' submitted')
                except Exception as e:
                    print(err)
                    applog.exception(e)
                    sys.exit(1)
            break
        elif reply.lower() in ('n', 'no'):
            print('Transaction cancelled')
            applog.info('Transaction cancelled!')
            sys.exit(0)
        else:
            print('Invalid answer, please input "y" or "n":')

    """
    Write some variables to files for debugging
    """
    with open(FILES_PATH + '/' + str(expire) + '_amounts.json', 'w') as f:
        f.write(json.dumps(AMOUNTS))
    with open(FILES_PATH + '/' + str(expire) + '_dst_addresses.json', 'w') as f:
        f.write(json.dumps(DST_ADDRESSES))

    """
    First part is now complete. The required input UTxOs for the airdrop were created in the previous transaction.
    Now we have to wait for the transaction to be adopted in a block before we do the airdrop transactions.
    """
    found = False
    src_token_trans = []
    while not found:
        print('waiting for transaction %s to be adopted...' % TXID)
        sleep(SLEEP_TIMEOUT)
        src_trans, src_token_trans, tok_amounts, out, err = get_transactions(src_addr)
        if err:
            print(err)
            applog.error(err)
            sys.exit(1)
        else:
            for t in src_token_trans:
                if t['hash'] == TXID:
                    found = True
                    break

    # the expected transaction was found
    print('Transaction %s adopted, continuing airdrop' % TXID)
    applog.info('Transaction %s adopted, continuing airdrop' % TXID)

    # query tip to update the transaction validity
    if len(MAGIC_NUMBER) == 0:
        cmd = ["cardano-cli", "query", "tip", CARDANO_NET]
    else:
        cmd = ["cardano-cli", "query", "tip", CARDANO_NET, str(MAGIC_NUMBER)]
    out, err = cardano_cli_cmd(cmd)

    # set transaction new expire time in TRANSACTION_EXPIRE seconds (default 86400 = 1 day)
    expire = json.loads(out)['slot'] + TRANSACTION_EXPIRE

    """
    For each transaction of the aidrop, search for the input we created in the first transaction 
    """
    count = 0
    for transaction in transactions:
        count += 1
        # ['inputs', 'outputs', 'change_address', 'total_amounts']
        lovelace_amount = int(transaction['total_amounts']['lovelace'])
        tokens_amount = int(transaction['total_amounts'][TOKEN_NAME])
        i_found = False
        for t in src_token_trans:
            for token in t['amounts']:
                if token['token'] == 'lovelace' and lovelace_amount + EXTRA_LOVELACE != int(token['amount']):
                    continue
                elif token['token'] == TOKEN_NAME and tokens_amount != int(token['amount']):
                    continue
                elif token['token'] != TOKEN_NAME:
                    continue
                # found the right UTxO
                i_found = True
                i = {}
                i['hash'] = t['hash']
                i['id'] = t['id']
                transaction['inputs'].append(i)
                src_token_trans.remove(t)
                break
            if i_found:
                break

    """
    Write some variables to files for debugging
    """
    with open(FILES_PATH + '/' + str(expire) + '_inputs.json', 'w') as f:
        f.write(json.dumps(src_token_trans))
    with open(FILES_PATH + '/' + str(expire) + '_transactions.json', 'w') as f:
        f.write(json.dumps(transactions))

    # transactions list created
    # now create the raw transaction files sign them and encode them as cbor files
    count = 0
    for transaction in transactions:
        count += 1
        cmd = ['cardano-cli', 'transaction', 'build']
        trans_filename_prefix = TRANSACTIONS_PATH + '/tx' + str(count)
        # add the inputs
        for t in transaction['inputs']:
            cmd.append('--tx-in')
            cmd.append(t['hash'] + '#' + t['id'])
        for t in transaction['outputs']:
            cmd.append('--tx-out')
            cmd.append(t['address'] + '+' + str(t['lovelace']) + '+' +
                       str(t[TOKEN_NAME]) + ' ' + TOKEN_NAME + '')
        cmd.append('--change-address')
        cmd.append(transaction['change_address'])
        cmd.append('--invalid-hereafter')
        cmd.append(str(expire))
        cmd.append('--out-file')
        cmd.append(trans_filename_prefix + '.raw')
        cmd.append(CARDANO_NET)
        if len(MAGIC_NUMBER) != 0:
            cmd.append(str(MAGIC_NUMBER))
        out, err = cardano_cli_cmd(cmd)
        if err:
            print(err)
            applog.error(err)
            sys.exit(1)
        print(out)
        applog.info(out)

        # sign transaction
        _, err = sign_transaction(SRC_KEYS, trans_filename_prefix + '.raw', trans_filename_prefix + '.signed')
        if err:
            print(err)
            sys.exit(1)

        # get the transaction id
        cmd = ["cardano-cli", "transaction", "txid", "--tx-file", trans_filename_prefix + '.signed']
        # execute the command
        out, err = cardano_cli_cmd(cmd)
        if err:
            print(err)
            sys.exit(1)
        TXID = out.strip()
        print('Transaction ID: %s' % TXID)
        applog.info('Transaction ID: %s' % TXID)

        # encode transactions in cbor format
        cmd = 'jq .cborHex ' + trans_filename_prefix + '.signed | xxd -r -p > ' + trans_filename_prefix + '.signed.cbor'
        stream = os.popen(cmd)
        out = stream.read().strip()
        print(out)

    # list the cbor transaction files
    for i in range(count):
        trans_filename_prefix = TRANSACTIONS_PATH + '/tx' + str(i + 1)
        cmd = 'ls -l ' + trans_filename_prefix + '.signed.cbor'
        stream = os.popen(cmd)
        out = stream.read().strip()
        print(out)

    # submit the transaction files using the submit-api url
    while True:
        reply = input('Confirm? [y/n] ')
        if reply.lower() in ('y', 'yes'):
            for i in range(count):
                trans_filename_prefix = TRANSACTIONS_PATH + '/tx' + str(i + 1)
                if SUBMITAPI_URL == '':
                    # submit transaction to the local node
                    if len(MAGIC_NUMBER) == 0:
                        cmd = ["cardano-cli", "transaction", "submit", "--tx-file",
                            trans_filename_prefix + '.signed', CARDANO_NET]
                    else:
                        cmd = ["cardano-cli", "transaction", "submit", "--tx-file", trans_filename_prefix +
                            '.signed', CARDANO_NET, str(MAGIC_NUMBER)]
                    out, err = cardano_cli_cmd(cmd)
                    if err:
                        print(err)
                        sys.exit(1)
                    print('Transaction executed')
                    print(out)
                    applog.info(out)
                else:
                    try:
                        # read transaction from file
                        with open(trans_filename_prefix + '.signed.cbor', 'rb') as f:
                            data = f.read()
                        # submit the transaction
                        headers = {'Accept': '*/*', 'Content-Type': 'application/cbor'}
                        response = requests.post(SUBMITAPI_URL, data=data, headers=headers)
                        applog.info(response.text + ' submitted')
                        print(str(response.status_code) + ' ' + response.text + ' submitted')
                    except Exception as e:
                        print(err)
                        applog.exception(e)
                        sys.exit(1)
            break
        elif reply.lower() in ('n', 'no'):
            print('Transactions cancelled')
            applog.info('Transactions cancelled!')
            sys,exit(0)
            break
        else:
            print('Invalid answer, please input "y" or "n":')
