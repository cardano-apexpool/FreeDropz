import subprocess
import json
from config import *

def parse_airdrop_data(data):
    """
    parse the airdrop data
    """
    airdrops_list = []
    out = ''
    err = ''
    try:
        json_data = json.loads(data)
        for item in json_data:
            address = list(item.keys())[0]
            amount = list(item.values())[0]
            aird = {}
            aird['address'] = address
            aird['tokens_amount'] = amount
            airdrops_list.append(aird)
        out = 'json parsed'
    except json.decoder.JSONDecodeError:
        for line in data.splitlines():
            wallet = line.split(',')
            item = {}
            item['address'] = wallet[0]
            item['tokens_amount'] = wallet[1]
            airdrops_list.append(item)
        out = 'csv parsed'
    except Exception as e:
        err = 'exception parsing data: %s' % str(e)
        return airdrops_list, [], [], [], out, err


    """
    DST_ADDRESSES = list of destination wallet addresses for the airdrop
    AMOUNTS = dictionary of wallet addresses and amounts to airdrop for each wallet address
    """
    dst_addresses = []
    amounts = {}
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
        amounts[address] = amount
        dst_addresses.append(address)

    spend_amounts = {}
    spend_amounts['lovelace'] = total_lovelace
    spend_amounts[TOKEN_NAME] = total_tokens
    return airdrops_list, spend_amounts, dst_addresses, amounts, out, err


def generate_protocol_file():
    """
    generate the protocol file
    """
    if len(MAGIC_NUMBER) == 0:
        cmd = ["cardano-cli", "query", "protocol-parameters", CARDANO_NET, "--out-file", PROTOCOL_FILE]
    else:
        cmd = ["cardano-cli", "query", "protocol-parameters", CARDANO_NET, str(MAGIC_NUMBER),
            "--out-file", PROTOCOL_FILE]
    out, err = cardano_cli_cmd(cmd)
    return out, err


def get_tip():
    """
    query tip
    """
    if len(MAGIC_NUMBER) == 0:
        cmd = ["cardano-cli", "query", "tip", CARDANO_NET]
    else:
        cmd = ["cardano-cli", "query", "tip", CARDANO_NET, str(MAGIC_NUMBER)]
    out, err = cardano_cli_cmd(cmd)
    return out, err


def get_available_amounts(src_addresses):
    """
    Get the amount of available ADA and tokens at the src_addresses
    """
    # source UTxOs grouped by source address
    source_transactions = {}
    # get the list of transactions from all source addresses
    src_transactions = []
    src_token_transactions = []
    tokens_amounts = []
    for src_addr in src_addresses:
        src_trans, src_token_trans, tok_amounts, out, err = get_transactions(src_addr)
        if err:
            msg = {}
            msg['error'] = err
            return [], [], [], [], msg
        else:
            utxos = {}
            utxos['src_transactions'] = src_trans
            utxos['src_token_transactions'] = src_token_trans
            source_transactions[src_addr] = utxos
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
    return source_transactions, src_transactions, src_token_transactions, tokens_amounts, ''


def get_utxo_list(address):
    """
    Get the list of UTxOs from the given addresses.
    :param address: Cardano Blockchain address to search for UTXOs
    :return: utxo_list: list of UTxOs
    """
    if len(MAGIC_NUMBER) == 0:
        cmd = ["cardano-cli", "query", "utxo", "--address", address, CARDANO_NET]
    else:
        cmd = ["cardano-cli", "query", "utxo", "--address", address, CARDANO_NET, str(MAGIC_NUMBER)]
    out, err = cardano_cli_cmd(cmd)
    utxo_list = []
    if not err:
        for line in out.splitlines():
            if 'lovelace' in line:
                trans = line.split()
                utxo_list.append(trans[0])
    return utxo_list


def get_transactions(address, max_utxos=MAX_IN_UTXOS):
    """
    Get the list of transactions from the given addresses. They will be used as input UTxOs.
    :param address: Cardano Blockchain address to search for UTXOs
    :param max_utxos: Maximum number of UTxOs to read from the address. if the number is too big,
        the transaction size will be over the maximum transaction size allowed by Cardano.
    :return: ada_transactions, token_transactions
            ada_transactions: list of transactions with lovelace only
            token_transactions: list of transactions including custom tokens
    """
    if len(MAGIC_NUMBER) == 0:
        cmd = ["cardano-cli", "query", "utxo", "--address", address, CARDANO_NET]
    else:
        cmd = ["cardano-cli", "query", "utxo", "--address", address, CARDANO_NET, str(MAGIC_NUMBER)]
    out, err = cardano_cli_cmd(cmd)
    tokens_amounts = {}
    ada_transactions = []
    token_transactions = []
    nr_utxos = 0
    if not err:
        for line in out.splitlines():
            nr_utxos += 1
            # exit loop if the max number of UTxOs has been reached
            if nr_utxos > max_utxos:
                break
            if 'lovelace' in line:
                transaction = {}
                trans = line.split()
                # if this is an UTxO with only lovelace in it
                if len(trans) == 6:
                    transaction['hash'] = trans[0]
                    transaction['id'] = trans[1]
                    transaction['amount'] = trans[2]
                    ada_transactions.append(transaction)
                    # add the lovelace to total amounts to spend
                    if 'lovelace' in tokens_amounts:
                        tokens_amounts['lovelace'] += int(transaction['amount'])
                    else:
                        tokens_amounts['lovelace'] = int(transaction['amount'])
                # if there are also other tokens
                else:
                    transaction['hash'] = trans[0]
                    transaction['id'] = trans[1]
                    transaction['amounts'] = []
                    tr_amount = {}
                    tr_amount['token'] = trans[3]
                    tr_amount['amount'] = trans[2]
                    transaction['amounts'].append(tr_amount)
                    # for each token
                    for i in range(0, int((len(trans) - 4) / 3)):
                        tr_amount = {}
                        tr_amount['token'] = trans[3 + i * 3 + 3]
                        tr_amount['amount'] = trans[3 + i * 3 + 2]
                        transaction['amounts'].append(tr_amount)
                    token_transactions.append(transaction)
                    # add the tokens to total amounts to spend
                    for t in transaction['amounts']:
                        if t['token'] in tokens_amounts:
                            tokens_amounts[t['token']] += int(t['amount'])
                        else:
                            tokens_amounts[t['token']] = int(t['amount'])
    return ada_transactions, token_transactions, tokens_amounts, out, err


def get_airdrop_details(cur, airdrop_id):
    """
    Return all the details about an airdrop from the database
    :param airdrop_id:
    :return: a disctionary with all the airdrop details
    """
    airdrop_details = {}
    airdrop_transactions = []
    cur.execute("SELECT hash, status, date, id FROM airdrops WHERE id = ?", (airdrop_id, ))
    airdrop = cur.fetchone()
    airdrop_details['airdrop_id'] = airdrop[0]
    airdrop_details['status'] = airdrop[1]
    airdrop_details['date'] = airdrop[2]
    cur.execute("SELECT hash, name, status, date FROM transactions WHERE airdrop_id = ?", (airdrop[3], ))
    transactions = cur.fetchall()
    for trans in transactions:
        airdrop_transaction = {}
        airdrop_transaction['transaction_hash'] = trans[0]
        airdrop_transaction['transaction_name'] = trans[1]
        airdrop_transaction['transaction_status'] = trans[2]
        airdrop_transaction['transaction_data'] = trans[3]
        airdrop_transactions.append(airdrop_transaction)
    airdrop_details['transactions'] = airdrop_transactions
    return airdrop_details


def validate_transaction(spend_amounts, tokens_amounts):
    """
    A transaction is considered valid here if the amounts of tokens
    in the source UTXOs  are greater than or equal to the amounts to spend.
    :param spend_amounts: amounts to spend
    :param tokens_amounts: existing amounts to spend from
    :return: True if transaction is valid, otherwise False
    """
    for am in spend_amounts:
        if am not in tokens_amounts or spend_amounts[am] > tokens_amounts[am]:
            return False
    return True


def sign_transaction(payment_skeys, infile, outfile):
    """
    Sign a raw transaction file.
    :param payment_skeys: payment signing keys
    :param infile: transaction raw file
    :param outfile: transaction signed file
    :return:
    """
    cmd = ["cardano-cli", "transaction", "sign", "--tx-body-file", infile]
    for pkey in payment_skeys:
        cmd += ["--signing-key-file", pkey]
    if len(MAGIC_NUMBER) == 0:
        cmd += [CARDANO_NET, "--out-file", outfile]
    else:
        cmd += [CARDANO_NET, str(MAGIC_NUMBER), "--out-file", outfile]
    out, err = cardano_cli_cmd(cmd)
    return out, err


def cardano_cli_cmd(cmd):
    """
    Execute a cardano-cli command.
    :param cmd: command to execute
    :return: output of the command and error message, if any
    """
    out, err = subprocess.Popen(
        cmd, env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).communicate()
    out = out.decode('utf-8')
    err = err.decode('utf-8')
    """
    if err and 'Warning' not in err and 'Ok.' not in err:
        print(cmd)
        print(err)
        sys.exit(1)
    """
    return out, err
