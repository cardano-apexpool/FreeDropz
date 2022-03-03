import sys
import threading
from http import HTTPStatus
from flask import Flask, request
from flask_restx import Api, Resource, reqparse
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.datastructures import FileStorage
import requests
import hashlib
from library import *
import sqlite3
import logging.handlers
import datetime
from time import sleep


app = Flask(__name__)
app.config['DEBUG'] = True
app.config['UPLOAD_FOLDER'] = FILES_PATH
app.wsgi_app = ProxyFix(app.wsgi_app)
api = Api(app, version='0.1', title='FreeDropz API', description='A simple API for FreeDropz',)
ns = api.namespace('api/v0', description='Airdrop operations')

test_parser = reqparse.RequestParser()
test_parser.add_argument('token_policy', type=str, help='Token policy', required=True)
test_parser.add_argument('token_name', type=str, help='Token name', required=True)

airdrop_details_parser = reqparse.RequestParser()
airdrop_details_parser.add_argument('airdrop_hash', type=str, help='Airdrop hash', required=True)

airdrop_parser = reqparse.RequestParser()
airdrop_parser.add_argument('airdrop_file', type=FileStorage, location=FILES_PATH, required=True)


@ns.route('/')
class Home(Resource):
    def get(self):
        return "<h1>FreeDropz API</h1>"


"""
@ns.route('/test')
@api.response(HTTPStatus.OK.value, "OK")
@api.response(HTTPStatus.NOT_ACCEPTABLE.value, "Not Acceptable client error")
@api.response(HTTPStatus.SERVICE_UNAVAILABLE.value, "Server error")
@api.doc(parser=test_parser)
class Test(Resource):
    def get(self):
        args = test_parser.parse_args()
        return "<h1>FreeDropz API</p><br>Token: %s.%s" % (args['token_policy'], args['token_name'])
"""


@ns.route('/airdrop_details')
@api.response(HTTPStatus.OK.value, "OK")
@api.response(HTTPStatus.NOT_ACCEPTABLE.value, "Not Acceptable client error")
@api.response(HTTPStatus.SERVICE_UNAVAILABLE.value, "Server error")
@api.doc(parser=airdrop_details_parser)
class Test(Resource):
    def get(self):
        args = airdrop_details_parser.parse_args()
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT max(id) FROM airdrops WHERE hash = ?", (args['airdrop_hash'],))
        airdrop_id = cur.fetchone()[0]
        airdrop_details = get_airdrop_details(cur, airdrop_id)
        conn.close()
        return airdrop_details


@ns.route('/validate')
@api.response(HTTPStatus.OK.value, "OK")
@api.response(HTTPStatus.NOT_ACCEPTABLE.value, "Not Acceptable client error")
@api.response(HTTPStatus.SERVICE_UNAVAILABLE.value, "Server error")
@api.doc(parser=airdrop_parser)
class EventValidate(Resource):
    def post(self):
        try:
            if request.data:
                data = request.data
            elif len(request.files) > 0:
                args = airdrop_parser.parse_args()
                if 'multipart/form-data' in request.content_type:
                    args['airdrop_file'].save(FILES_PATH + '/airdrop_file.json')
                    with open('files/airdrop_file.json', 'r') as f:
                        data = f.read()
                else:
                    applog.error('Unsupported data type')
                    msg = {}
                    msg['error'] = 'Unsupported data type'
                    return msg, 406
            else:
                msg = {}
                msg['error'] = 'Not Acceptable client error'
                return msg, 406
        except Exception as e:
            applog.exception(e)
            msg = {}
            msg['error'] = 'Not Acceptable client error'
            return msg, 406
        airdrops_list, spend_amounts, dst_addresses, amounts, out, err = parse_airdrop_data(data)
        if err:
            msg = {}
            msg['error'] = 'err'
            return msg, 406
        else:
            applog.info(out)
            applog.info('Airdrop information from the airdrops file:')
            applog.info('%d airdrops' % len(airdrops_list))
            applog.info('total lovelace: %d' % spend_amounts['lovelace'])
            applog.info('total tokens: %d' % spend_amounts[TOKEN_NAME])

        # read the keys and the addresses (where the tokens and lovelace are) from the files
        try:
            first_key = SRC_KEYS[0]
        except Exception as err:
            applog.exception('Error reading SRC_KEYS %s: %s' % (SRC_KEYS, err))
            msg = {}
            msg['error'] = 'Error reading SRC_KEYS %s: %s' % (SRC_KEYS, err)
            return msg, 503

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
                applog.exception('Error while opening the file %s: %s' % (address_file, err))
                msg = {}
                msg['error'] = 'Error opening the file %s: %s' % (address_file, err)
                return msg, 503

        # read the change address from the file
        change_address = ''
        try:
            with open(CHANGE_ADDRESS, 'r') as f:
                change_address = f.read()
        except Exception as err:
            applog.exception('Error while opening the file %s: %s' % (CHANGE_ADDRESS, err))
            return 'Error opening the file %s: %s' % (CHANGE_ADDRESS, err), 503

        # get available amounts at the src_addresses
        source_transactions, src_transactions, src_token_transactions, tokens_amounts, \
            err = get_available_amounts(src_addresses)
        if err:
            applog.error(err)
            return err, 503

        # debug
        if len(src_transactions) == 0 and len(src_token_transactions) == 0:
            applog.error('No source transactions (UTXOs)!')
            msg = {}
            msg['error'] = 'No source transactions (UTXOs)!'
            return msg, 503
        applog.info('Source transactions: %s' % src_transactions)
        applog.info('Source token transactions: %s' % src_token_transactions)
        applog.info('Amounts available: %s' % tokens_amounts)
        applog.info('Amounts to spend: %s' % spend_amounts)

        # validate transaction
        if not validate_transaction(spend_amounts, tokens_amounts):
            applog.error('Spending more than existing amounts is not possible!')
            msg = {}
            msg['spend_amounts'] = spend_amounts
            msg['available_amounts'] = tokens_amounts
            msg['error'] = 'Spending more than existing amounts is not possible!'
            return msg, 406
        else:
            extra_ada = int(len(airdrops_list) / ADDRESSES_PER_TRANSACTION * (860000 + EXTRA_LOVELACE) / 1000000 + 1)
            applog.error('Transaction is possible - available amounts are more than the amounts to spend.')
            if spend_amounts['lovelace'] + extra_ada * 1000000 > tokens_amounts['lovelace']:
                applog.error('Please be sure there are about %d extra ADA in the source address.\n' % extra_ada)
        applog.info('source_transactions: %s\n' % source_transactions)

        msg = {}
        msg['spend_amounts'] = spend_amounts
        msg['available_amounts'] = tokens_amounts
        msg['message'] = 'Transaction is possible - available amounts are more than the amounts to spend. '
        msg['message'] += 'Please be sure there are about %d extra ADA in the source address.' % extra_ada
        return msg


@ns.route('/submit')
@api.response(HTTPStatus.OK.value, "OK")
@api.response(HTTPStatus.NOT_ACCEPTABLE.value, "Not Acceptable client error")
@api.response(HTTPStatus.SERVICE_UNAVAILABLE.value, "Server error")
@api.doc(parser=airdrop_parser)
class EventSubmit(Resource):
    def post(self):
        try:
            if request.data:
                data = request.data
            elif len(request.files) > 0:
                args = airdrop_parser.parse_args()
                if 'multipart/form-data' in request.content_type:
                    args['airdrop_file'].save(FILES_PATH + '/airdrop_file.json')
                    with open('files/airdrop_file.json', 'r') as f:
                        data = f.read()
                else:
                    applog.error('Unsupported data type')
                    msg = {}
                    msg['error'] = 'Unsupported data type'
                    return msg, 406
            else:
                msg = {}
                msg['error'] = 'Not Acceptable client error'
                return msg, 406
        except Exception as e:
            applog.exception(e)
            msg = {}
            msg['error'] = 'Not Acceptable client error'
            return msg, 406

        airdrop_id = hashlib.sha256(str(data).encode()).hexdigest()
        applog.info('airdrop_id: %s' % airdrop_id)
        airdrops_list, spend_amounts, dst_addresses, amounts, out, err = parse_airdrop_data(data)
        if err:
            msg = {}
            msg['error'] = 'err'
            return msg, 406
        else:
            applog.info(out)
            applog.info('Airdrop information from the airdrops file:')
            applog.info('%d airdrops' % len(airdrops_list))
            applog.info('total lovelace: %d' % spend_amounts['lovelace'])
            applog.info('total tokens: %d' % spend_amounts[TOKEN_NAME])

        # read the keys and the addresses (where the tokens and lovelace are) from the files
        try:
            first_key = SRC_KEYS[0]
        except Exception as err:
            applog.exception('Error reading SRC_KEYS %s: %s' % (SRC_KEYS, err))
            msg = {}
            msg['error'] = 'Error reading SRC_KEYS %s: %s' % (SRC_KEYS, err)
            return msg, 503

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
                applog.exception('Error while opening the file %s: %s' % (address_file, err))
                msg = {}
                msg['error'] = 'Error opening the file %s: %s' % (address_file, err)
                return msg, 503

        # read the change address from the file
        change_address = ''
        try:
            with open(CHANGE_ADDRESS, 'r') as f:
                change_address = f.read()
        except Exception as err:
            applog.exception('Error while opening the file %s: %s' % (CHANGE_ADDRESS, err))
            return 'Error opening the file %s: %s' % (CHANGE_ADDRESS, err), 503

        # get available amounts at the src_addresses
        source_transactions, src_transactions, src_token_transactions, tokens_amounts, \
            err = get_available_amounts(src_addresses)
        if err:
            applog.error(err)
            return err, 503

        # debug
        if len(src_transactions) == 0 and len(src_token_transactions) == 0:
            applog.error('No source transactions (UTXOs)!')
            msg = {}
            msg['error'] = 'No source transactions (UTXOs)!'
            return msg, 503
        applog.info('Source transactions: %s' % src_transactions)
        applog.info('Source token transactions: %s' % src_token_transactions)
        applog.info('Amounts available: %s' % tokens_amounts)
        applog.info('Amounts to spend: %s' % spend_amounts)

        # validate transaction
        if not validate_transaction(spend_amounts, tokens_amounts):
            applog.error('Spending more than existing amounts is not possible!')
            msg = {}
            msg['spend_amounts'] = spend_amounts
            msg['available_amounts'] = tokens_amounts
            msg['error'] = 'Spending more than existing amounts is not possible!'
            return msg, 406
        else:
            extra_ada = int(len(airdrops_list) / ADDRESSES_PER_TRANSACTION * (860000 + EXTRA_LOVELACE) / 1000000 + 1)
            applog.info('Transaction is possible - available amounts are more than the amounts to spend.')
            if spend_amounts['lovelace'] + extra_ada * 1000000 > tokens_amounts['lovelace']:
                applog.error('Please be sure there are about %d extra ADA in the source address.\n' % extra_ada)
        applog.info('source_transactions: %s\n' % source_transactions)
        """
        Return the response, but continue the airdrop in a separate thread
        """

        airdrop_thread = threading.Thread(target=airdrop, args=(dst_addresses, amounts, change_address,
                                                                src_transactions, src_token_transactions,
                                                                first_src_address, tokens_amounts, spend_amounts,
                                                                airdrop_id,))
        airdrop_thread.start()
        msg = {}
        msg['spend_amounts'] = spend_amounts
        msg['available_amounts'] = tokens_amounts
        msg['airdrop_id'] = airdrop_id
        msg['message'] = 'Transaction is possible - available amounts are more than the amounts to spend. '
        msg['message'] += 'Please be sure there are about %d extra ADA in the source address.' % extra_ada
        return msg


def airdrop(dst_addresses, amounts, change_address, src_transactions, src_token_transactions,
            first_src_address, tokens_amounts, spend_amounts, airdrop_hash):
        """
        Create the airdrop transactions list in memory
        """

        out, err = generate_protocol_file()
        if err and 'Warning' not in err and 'Ok.' not in err:
            msg = {}
            msg['error'] = err.strip()
            return msg, 503

        out, err = get_tip()
        if err and 'Warning' not in err and 'Ok.' not in err:
            msg = {}
            msg['error'] = err.strip()
            return msg, 503
        # set transaction expire time in TRANSACTION_EXPIRE seconds (default 86400 = 1 day)
        expire = json.loads(out)['slot'] + TRANSACTION_EXPIRE

        transactions = []
        transaction = {}
        inputs = []
        outputs = []
        # change_address = src_addr
        trans_lovelace = 0
        trans_tokens = 0
        count = 0
        # for the totals of all transactions
        amount_lovelace = 0
        amount_tokens = 0
        for address in dst_addresses:
            count += 1
            output = {}
            output['address'] = address
            output['lovelace'] = amounts[address][0]['amount']
            output[TOKEN_NAME] = amounts[address][1]['amount']
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

        applog.debug('Number of transactions to do: %d' % len(transactions))
        applog.debug('Transactions list:')
        t_cnt = 0
        for t in transactions:
            t_cnt += 1
            applog.debug('Transaction %d: %s' % (t_cnt, t))
        # debug
        applog.info('total lovelace in transactions: %d' % amount_lovelace)
        applog.info('total tokens in transactions: %d' % amount_tokens)

        """
        Write the airdrop information and the transaction information in the database
        """
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        now = datetime.datetime.now()
        cur.execute("INSERT INTO airdrops (hash, tokens_name, status, date) VALUES (?, ?, ?, ?)",
                    (airdrop_hash, TOKEN_NAME, 'utxo create transaction start', now))
        conn.commit()
        airdrop_id = cur.lastrowid

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
            applog.error(err)
            msg = {}
            msg['error'] = 'Server error: %s' % err
            return msg, 503
        applog.info(out)

        # get the transaction id
        cmd = ["cardano-cli", "transaction", "txid", "--tx-body-file", TRANSACTIONS_PATH + '/tx.raw']
        # execute the command
        out, err = cardano_cli_cmd(cmd)
        if err:
            applog.error(err)
            msg = {}
            msg['error'] = 'Server error: %s' % err
            return msg, 503
        txid = out.strip()
        applog.info('Transaction ID: %s' % txid)

        """
        Insert the transaction into the database
        """
        now = datetime.datetime.now()
        cur.execute("INSERT INTO transactions (airdrop_id, hash, name, status, date) VALUES (?, ?, ?, ?, ?)",
                    (airdrop_id, txid, 'utxo_transaction', 'transaction created', now))
        cur.execute("UPDATE airdrops SET status = 'utxo transaction created', date = ? WHERE id = ?", (now, airdrop_id))
        conn.commit()
        trans_id = cur.lastrowid

        # sign transaction
        _, err = sign_transaction(SRC_KEYS, TRANSACTIONS_PATH + '/tx.raw', TRANSACTIONS_PATH + '/tx.signed')
        if err:
            applog.error(err)
            msg = {}
            msg['error'] = 'Server error: %s' % err
            return msg, 503
        """
        Update the transaction status - signed
        """
        now = datetime.datetime.now()
        cur.execute("UPDATE transactions SET status = 'transaction signed', date = ? WHERE id = ?", (now, trans_id))
        cur.execute("UPDATE airdrops SET status = 'utxo transaction signed', date = ? WHERE id = ?", (now, airdrop_id))
        conn.commit()

        # encode transactions in cbor format
        cmd = 'jq .cborHex ' + TRANSACTIONS_PATH + '/tx.signed | xxd -r -p > ' + TRANSACTIONS_PATH + '/tx.signed.cbor'
        stream = os.popen(cmd)
        out = stream.read().strip()
        applog.debug(out)

        """
        Update the transaction status - cbor encoded
        """
        now = datetime.datetime.now()
        cur.execute("UPDATE transactions SET status = 'transaction cbor encoded', date = ? WHERE id = ?",
                    (now, trans_id))
        cur.execute("UPDATE airdrops SET status = 'utxo transaction cbor encoded', date  = ? WHERE id = ?",
                    (now, airdrop_id))
        conn.commit()

        # list the transaction file on disk, to see that everything is fine
        # and that the size is ok (less than the maximum transaction size of 16 KB)
        cmd = 'ls -l ' + TRANSACTIONS_PATH + '/tx.signed.cbor'
        stream = os.popen(cmd)
        out = stream.read().strip()
        applog.debug(out)

        # ask for confirmation before sending the transaction
        while True:
            reply = 'y' # input('Confirm? [y/n] ')
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
                        applog.error(err)
                        """
                        Update the transaction status - error
                        """
                        now = datetime.datetime.now()
                        cur.execute("UPDATE transactions SET status = 'submit error: ?', date = ? WHERE id = ?",
                                    (err, now, trans_id))
                        cur.execute("UPDATE airdrops SET status = 'utxo transaction submit error', "
                                    "date = ? WHERE id = ?", (now, airdrop_id))
                        conn.commit()
                        msg = {}
                        msg['error'] = 'Server error: %s' % err
                        return msg, 503

                    applog.info('Transaction %s submitted' % txid)
                    applog.info(out)
                else:
                    try:
                        # read transaction from file
                        with open(TRANSACTIONS_PATH + '/tx.signed.cbor', 'rb') as f:
                            data = f.read()
                        # submit the transaction to the submit-api url
                        headers = {'Accept': '*/*', 'Content-Type': 'application/cbor'}
                        response = requests.post(SUBMITAPI_URL, data=data, headers=headers)
                        if response.status_code != 202:
                            applog.error(str(response.status_code) + ' ' + response.text)
                            """
                            Update the transaction status - error
                            """
                            now = datetime.datetime.now()
                            cur.execute("UPDATE transactions SET status = 'submit error: ?', date = ? WHERE id = ?",
                                        (response.text, now, trans_id))
                            cur.execute("UPDATE airdrops SET status = 'utxo transaction submit error', "
                                        "date = ? WHERE id = ?", (now, airdrop_id))
                            conn.commit()
                            msg = {}
                            msg['error'] = 'Server error: %s' % response.text
                            return msg, response.status_code
                        else:
                            applog.info('%s transaction %s submitted' % (str(response.status_code),
                                                                         response.text.strip('"')))
                    except Exception as e:
                        applog.error(err)
                        applog.exception(e)
                        """
                        Update the transaction status - exception
                        """
                        now = datetime.datetime.now()
                        cur.execute("UPDATE transactions SET status = 'submit exception: ?', date = ? WHERE id = ?",
                                    (str(e), now, trans_id))
                        cur.execute("UPDATE airdrops SET status = 'utxo transaction submit exception', "
                                    "date = ? WHERE id = ?", (now, airdrop_id))
                        conn.commit()
                        msg = {}
                        msg['error'] = 'Server error: %s' % err
                        return msg, 503
                break
            elif reply.lower() in ('n', 'no'):
                applog.info('Transaction cancelled!')
                msg = {}
                msg['error'] = 'Transaction cancelled'
                return msg, 503
            else:
                print('Invalid answer, please input "y" or "n":')

        """
        Update the transaction status - submitted
        """
        now = datetime.datetime.now()
        cur.execute("UPDATE transactions SET status = 'transaction submitted', date = ? WHERE id = ?",
                    (now, trans_id))
        cur.execute("UPDATE airdrops SET status = 'utxo transaction submitted', date = ? WHERE id = ?",
                    (now, airdrop_id))
        conn.commit()

        """
        Write some variables to files for debugging
        """
        try:
            with open(FILES_PATH + '/' + str(expire) + '_amounts.json', 'w') as f:
                f.write(json.dumps(amounts))
            with open(FILES_PATH + '/' + str(expire) + '_dst_addresses.json', 'w') as f:
                f.write(json.dumps(dst_addresses))
        except Exception as e:
            applog.exception(e)
        """
        First part is now complete. The required input UTxOs for the airdrop were created in the previous transaction.
        Now we have to wait for the transaction to be adopted in a block before we do the airdrop transactions.
        """
        found = False
        src_token_trans = []
        while not found:
            applog.info('waiting for transaction %s to be adopted...' % txid)
            sleep(SLEEP_TIMEOUT)
            src_trans, src_token_trans, tok_amounts, out, err = get_transactions(first_src_address)
            if err:
                applog.error(err)
                msg = {}
                msg['error'] = 'Server error: %s' % err
                return msg, 503
            else:
                for t in src_token_trans:
                    if t['hash'] == txid:
                        found = True
                        break

        # the expected transaction was found
        applog.info('Transaction %s adopted, continuing airdrop' % txid)
        """
        Update the transaction status - adopted
        """
        now = datetime.datetime.now()
        cur.execute("UPDATE airdrops SET status = 'utxo transaction adopted', date = ? WHERE id = ?",
                    (now, airdrop_id))
        cur.execute("UPDATE transactions SET status = 'transaction adopted', date = ? WHERE id = ?",
                    (now, trans_id))
        conn.commit()

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
                cmd.append(t['hash'] + '#' + str(t['id']))
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
                applog.error(err)
                now = datetime.datetime.now()
                cur.execute("UPDATE airdrops SET status = ?, date = ? WHERE id = ?",
                            ('error creating airdrop transactions: ' + err, now, airdrop_id))
                conn.commit()
                msg = {}
                msg['error'] = 'Server error: %s' % err
                return msg, 503
            applog.info(out)

            # sign transaction
            _, err = sign_transaction(SRC_KEYS, trans_filename_prefix + '.raw', trans_filename_prefix + '.signed')
            if err:
                applog.error(err)
                now = datetime.datetime.now()
                cur.execute("UPDATE airdrops SET status = ?, date = ? WHERE id = ?",
                            ('error signing airdrop transactions: ' + err, now, airdrop_id))
                conn.commit()
                msg = {}
                msg['error'] = 'Server error: %s' % err
                return msg, 503

            # get the transaction id
            cmd = ["cardano-cli", "transaction", "txid", "--tx-file", trans_filename_prefix + '.signed']
            # execute the command
            out, err = cardano_cli_cmd(cmd)
            if err:
                applog.error(err)
                msg = {}
                msg['error'] = 'Server error: %s' % err
                return msg, 503
            txid = out.strip()
            applog.info('Transaction ID: %s' % txid)

            """
            TO DO: see what errors could happen here and treat them
            """
            # encode transactions in cbor format
            cmd = 'jq .cborHex ' + trans_filename_prefix + '.signed | xxd -r -p > ' \
                  + trans_filename_prefix + '.signed.cbor'
            stream = os.popen(cmd)
            out = stream.read().strip()
            applog.info(out)

            now = datetime.datetime.now()
            cur.execute("INSERT INTO transactions (airdrop_id, hash, name, status, date) VALUES (?, ?, ?, ?, ?)",
                        (airdrop_id, txid, 'airdrop_transaction_' + str(count),
                         'transaction created, signed and encoded', now))
        conn.commit()

        # list the cbor transaction files
        for i in range(count):
            trans_filename_prefix = TRANSACTIONS_PATH + '/tx' + str(i + 1)
            cmd = 'ls -l ' + trans_filename_prefix + '.signed.cbor'
            stream = os.popen(cmd)
            out = stream.read().strip()
            applog.debug(out)

        now = datetime.datetime.now()
        cur.execute("UPDATE airdrops SET status = 'submitting airdrop transactions', date = ? WHERE id = ?",
                    (now, airdrop_id))
        conn.commit()

        transaction_ids = []
        # submit the transaction files using the submit-api url
        while True:
            reply = 'y' # input('Confirm? [y/n] ')
            if reply.lower() in ('y', 'yes'):
                submitted_transactions = []
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
                            applog.error(err)
                            """
                            Update the transaction status - error
                            """
                            now = datetime.datetime.now()
                            cur.execute("UPDATE airdrops SET status = 'exception submitting airdrop transactions: ?', "
                                        "date = ? WHERE id = ?", (err, now, airdrop_id))
                            conn.commit()
                            msg = {}
                            msg['error'] = 'Server error: %s' % err
                            return msg, 503
                        applog.info('Transaction submitted')
                        applog.info(out)

                        # get the transaction id
                        cmd = ["cardano-cli", "transaction", "txid", "--tx-file", trans_filename_prefix + '.signed']
                        # execute the command
                        out, err = cardano_cli_cmd(cmd)
                        if err:
                            applog.error(err)
                            msg = {}
                            msg['error'] = 'Server error: %s' % err
                            return msg, 503
                        txid = out.strip()

                        now = datetime.datetime.now()
                        cur.execute("UPDATE transactions SET status = 'transaction submitted', "
                                    "date = ? WHERE hash = ?", (now, txid))
                        conn.commit()
                        transaction_ids.append(txid)
                    else:
                        try:
                            # read transaction from file
                            with open(trans_filename_prefix + '.signed.cbor', 'rb') as f:
                                data = f.read()
                            # submit the transaction
                            headers = {'Accept': '*/*', 'Content-Type': 'application/cbor'}
                            response = requests.post(SUBMITAPI_URL, data=data, headers=headers)
                            message = 'Transaction ' + response.text.strip('"') + ' submitted'
                            applog.info(str(response.status_code) + ' ' + message)
                            submitted_transactions.append(response.text.strip('"'))
                            now = datetime.datetime.now()
                            cur.execute("UPDATE transactions SET status = 'transaction submitted', "
                                        "date = ? WHERE hash = ?", (now, response.text.strip('"')))
                            conn.commit()
                            transaction_ids.append(response.text.strip('"'))
                        except Exception as e:
                            applog.exception(e)
                            now = datetime.datetime.now()
                            cur.execute("UPDATE airdrops SET status = ?, date = ? WHERE id = ?",
                                        ('exception submitting airdrop transactions: ' + str(e), now, airdrop_id))
                            conn.commit()
                            msg = {}
                            msg['error'] = 'Server exception while submitting transaction: %s' % str(e)
                            return msg, 503
                break
            elif reply.lower() in ('n', 'no'):
                message = 'Transaction(s) cancelled'
                applog.info(message)
                msg = {}
                msg['error'] = message
                return msg, 503
            else:
                print('Invalid answer, please input "y" or "n":')

        now = datetime.datetime.now()
        cur.execute("UPDATE airdrops SET status = 'transactions submitted', date = ? WHERE id = ?",
                    (now, airdrop_id))
        conn.commit()
        msg = {}
        msg['message'] = 'Transaction(s) %s submitted' % ", ".join(submitted_transactions)

        """
        Waiting for the transactions to be adopted in one or more blocks.
        """
        found_utxo_list = []
        while True:
            applog.info('waiting for transaction(s) %s to be adopted...' % transaction_ids)
            sleep(SLEEP_TIMEOUT)
            utxo_list = get_utxo_list(change_address)
            if err:
                applog.error(err)
                msg = {}
                msg['error'] = 'Server error: %s' % err
                return msg, 503
            else:
                for utxo in utxo_list:
                    if utxo in transaction_ids and utxo not in found_utxo_list:
                        found_utxo_list.append(utxo)
                        applog.info('Transaction %s adopted' % utxo)
                        now = datetime.datetime.now()
                        cur.execute("UPDATE transactions SET status = 'transaction adopted', date = ? "
                                    "WHERE hash = ?", (now, utxo))
                        conn.commit()
                if len(transaction_ids) == len(found_utxo_list):
                    break
        applog.info('All airdrop transactions adopted')
        applog.info('Airdrop %s finished' % airdrop_hash)
        now = datetime.datetime.now()
        cur.execute("UPDATE airdrops SET status = 'airdrop finished successfully', date = ? WHERE id = ?",
                    (now, airdrop_id))
        conn.commit()
        airdrop_details = get_airdrop_details(cur, airdrop_id)
        msg = {}
        msg['message'] = 'All airdrop transactions adopted, airdrop %s finished' % airdrop_hash
        msg['details'] = airdrop_details

        conn.close()
        applog.info(msg)
        return msg


if __name__ == '__main__':
    """
    Set up logging
    """
    handler = logging.handlers.WatchedFileHandler(LOG_FILE)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    applog = logging.getLogger('airdrops')
    applog.addHandler(handler)
    applog.setLevel(logging.INFO)

    """
    create some required folders to store log and transaction file
    """
    try:
        if not os.path.exists(FILES_PATH):
            os.mkdir(FILES_PATH)
        if not os.path.exists(TRANSACTIONS_PATH):
            os.mkdir(TRANSACTIONS_PATH)
        if not os.path.exists(os.path.dirname(DB_NAME)):
            os.mkdir(os.path.dirname(DB_NAME))
    except Exception as e:
        applog.exception('Error creating the required folders: %s' % e)
        sys.exit(1)

    """
    Create database and tables if not already existing
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS airdrops (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                hash CHAR(64) NOT NULL,
                tokens_name CHAR(96),
                name CHAR(64),
                description TEXT,
                status TEXT,
                date timestamp
                )''')
    conn.commit()
    cur.execute('''CREATE INDEX IF NOT EXISTS airdrops_hash on airdrops(hash)''')
    conn.commit()

    cur.execute('''CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                airdrop_id INTEGER NOT NULL,
                hash CHAR(64) NOT NULL,
                name CHAR(64),
                description TEXT,
                status TEXT,
                date timestamp
                )''')
    conn.commit()
    cur.execute('''CREATE INDEX IF NOT EXISTS transactions_airdrop_id on transactions(airdrop_id)''')
    conn.commit()

    cur.execute('''CREATE TABLE IF NOT EXISTS transaction_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                transaction_id INTEGER NOT NULL,
                address CHAR(128) NOT NULL,
                amount_lovelace INTEGER,
                amount_tokens INTEGER,
                description TEXT,
                date timestamp
                )''')
    conn.commit()
    cur.execute(
        '''CREATE INDEX IF NOT EXISTS transaction_details_transaction_id on transaction_details(transaction_id)''')
    conn.commit()

    applog.info("*****************************************************************")
    applog.info('Starting')

    app.run(
        threaded=True,
        host='0.0.0.0',
        port=API_PORT
    )
