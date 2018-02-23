import os
import time
import uuid
import json

from distutils.util import strtobool
from neorpc.Client import RPCClient, RPCEnpoint
from neorpc.Settings import SettingsHolder
from redis import Redis


class NEOInterface():

    def __init__(self, use_privnet=True):

        settings = SettingsHolder()

        if use_privnet:

            addr_list = [
                "http://private_net:20332"
            ]

            settings.setup(addr_list)

        else:
            settings.setup_mainnet()

        self.neo_rpc_client = RPCClient(settings)
        self.rds = Redis(host='redis', port=6379, db=0)
        self.nm_auth_token = os.environ.get('NM_AUTH_TOKEN', None)

    def check_funds(self, address, amount, asset):

        account = None

        while not account:
            account = self.neo_rpc_client.get_account(address)

        balances = account['balances']

        for i in balances:
            if i['asset'] == asset:
                if int(i['value']) >= amount:
                    return True

        return False

    def check_transaction(self, sender, receiver, amount, asset, min_conf):

        height = None

        while not height:
            height = self.neo_rpc_client.get_height()

        time.sleep(1)
        block = None

        while not block:
            block = self.neo_rpc_client.get_block(height)
            if 'error' in block:
                if 'message' in block['error']:
                    if block['error']['message'] == 'Unknown block':
                        block = None

        confirmations = int(block['confirmations'])

        for i in block['tx']:
            if i['type'] == 'ContractTransaction':
                txid = i['txid']
                transaction = self.neo_rpc_client.get_transaction(txid)
                if transaction['vout'][0]['address'] == 'receiver':
                    if transaction['vout'][1]['address'] == 'sender':
                        if int(transaction['vout'][0]['value']) == int(amount):
                            if transaction['vout'][0] == asset:
                                if confirmations >= int(min_conf):
                                    return True

        return False

    def validate_addr(self, address):

        result = None

        while not result:
            result = self.neo_rpc_client.validate_addr(address)

        return result

    def address_to_hash(self, address):

        account = self.neo_rpc_client.get_account(address)
        script_hash = account['script_hash']

        return script_hash

    def add_milestone(self, dapp_script_hash, milestone_key, agreement,
                      neo_address_customer, neo_address_assignee, platform,
                      timestamp, utc_offset, neo_address_oracle, pay_out,
                      asset, threshold):

        params = {}
        params['milestone_key'] = milestone_key
        params['agreement'] = agreement
        customer_hash = self.address_to_hash(neo_address_customer)
        params['customer'] = customer_hash
        assignee_hash = self.address_to_hash(neo_address_assignee)
        params['assignee'] = assignee_hash
        params['platform'] = platform
        params['timestamp'] = timestamp
        params['utc_offset'] = utc_offset
        oracle_hash = self.address_to_hash(neo_address_oracle)
        params['oracle'] = oracle_hash
        params['pay_out'] = pay_out
        params['asset'] = asset
        params['threshold'] = threshold

        cmd_id = uuid.uuid4()
        operation = 'milestone'

        data = {
            'auth_token': self.nm_auth_token,
            'cmd_id': cmd_id,
            'operation': operation,
            'params': params
        }

        data = json.dumps(data)

        self.rds.publish('neo-cmd', data)

    def review_milestone(self, dapp_script_hash, milestone_key, score):

        params = {}
        params['milestone_key'] = milestone_key
        params['score'] = score

        cmd_id = uuid.uuid4()
        operation = 'review'

        data = {
            'auth_token': self.nm_auth_token,
            'cmd_id': cmd_id,
            'operation': operation,
            'params': params
        }

        data = json.dumps(data)

        self.rds.publish('neo-cmd', data)
