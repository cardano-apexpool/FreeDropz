import sys
import subprocess
from config import *


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
    if err and 'Warning' not in err and 'Ok.' not in err:
        print(cmd)
        print(err)
        sys.exit(1)
    return out, err
