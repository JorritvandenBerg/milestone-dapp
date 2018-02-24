import os
import binascii
import json
from redis import Redis
from logzero import logger


class CommandHandler():

    def __init__(self, smart_contract, cmd_id, operation, params):
        self.smart_contract
        self.rds = Redis(host='redis', port=6379, db=0)
        redis_auth_token = os.environ.get('REDIS_AUTH_TOKEN', None)

        if operation == 'milestone':
            self.milestone(cmd_id, params)

        elif operation == 'review':
            self.review(cmd_id, params)

        else:
            logger.error('Invalid command time %s', operation)
            response = {
                'cmd_id': cmd_id,
                'auth_token': redis_auth_token,
                'status': 'failed'
            }

            response = json.dumps(response)

            self.rds.publish('neo-response', response)

    def milestone(self, cmd_id, params):

        milestone_key = binascii.hexlify(params['milestone_key'].encode())
        agreement = binascii.hexlify(params['agreement'].encode())
        customer = binascii.hexlify(params['customer'].encode())
        assignee = binascii.hexlify(params['assignee'].encode())
        platform = binascii.hexlify(params['platform'].encode())
        timestamp = binascii.hexlify(params['timestamp'].encode())
        utc_offset = binascii.hexlify(params['utc_offset'].encode())
        oracle = binascii.hexlify(params['oracle'].encode())
        pay_out = binascii.hexlify(params['pay_out'].encode())
        asset = binascii.hexlify(params['asset'].encode())
        threshold = binascii.hexlify(params['threshold'].encode())

        self.smart_contract.add_invoke(
            "milestone", milestone_key, agreement, customer, assignee,
            platform, timestamp, utc_offset, oracle, pay_out, asset, threshold
        )

    def review(self, cmd_id, params):

        milestone_key = binascii.hexlify(params['milestone_key'].encode())
        score = binascii.hexlify(params['score'].encode())

        self.smart_contract.add_invoke("review", milestone_key, score)
