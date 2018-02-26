"""
Example of running a NEO node and receiving notifications when events
of a specific smart contract happen.
Events include Runtime.Notify, Runtime.Log, Storage.*, Execution.Success
and several more.
More documentation is coming soon.
"""
import os
import threading
import json
from redis import Redis
from time import sleep

from logzero import logger
from twisted.internet import reactor, task

from neo.Network.NodeLeader import NodeLeader
from neo.Core.Blockchain import Blockchain
from neo.Implementations.Blockchains.LevelDB.LevelDBBlockchain import LevelDBBlockchain
from neo.Settings import settings

from milestonecontract import MilestoneSmartContract
from handler import CommandHandler

# Use private net
settings.setup_privnet()

# If you want the log messages to also be saved in a logfile, enable the
# next line. This configures a logfile with max 10 MB and 3 rotations:
settings.set_logfile("/tmp/logfile.log", max_bytes=1e7, backup_count=3)

# Setup the smart contract instance
script_hash = os.environ.get('SCRIPT_HASH', None)
wallet_file = os.environ.get("WALLET_FILE", '/neo-python/neo-privnet.wallet')
wallet_pwd = os.getenv("WALLET_PWD", "coz")
smart_contract = MilestoneSmartContract(script_hash, wallet_file, wallet_pwd)

# Setup Redis
rds = Redis(host='redis', port=6379, db=0)
redis_auth_token = os.environ.get('REDIS_AUTH_TOKEN', None)

if not redis_auth_token:
    logger.error("REDIS_AUTH_TOKEN not set in secrets.env, aborting..")

def Listener():

    """ Custom code run in a background thread. This function is run in a
    daemonized thread, which means it can be instantly killed at any moment,
    whenever the main thread quits. If you need more safety, don't use a
    daemonized thread and handle exiting this thread in another way
    (eg. with signals and events).
    """

    channel = 'neo-cmd'
    p = rds.pubsub()
    p.subscribe(channel)

    logger.info('Started monitoring channel {0}'.format(channel))

    for msg in p.listen():

        try:
            data = json.loads(msg['data'])
            data = msg['data']
            cmd_id = data['cmd_id']
            operation = data['operation']
            params = data['params']
            auth_token = data['auth_token']

            if auth_token == redis_auth_token:
                logger.info("Block %s / %s  - dispatching %s command",
                            str(Blockchain.Default().Height),
                            str(Blockchain.Default().HeaderHeight), operation)

                CommandHandler(smart_contract, cmd_id, operation, params)

            else:
                logger.error("Block %s / %s  - unauthorized %s command",
                            str(Blockchain.Default().Height),
                            str(Blockchain.Default().HeaderHeight), operation)

                response = {
                    'cmd_id': cmd_id,
                    'auth_token': redis_auth_token,
                    'status': 'failed'
                }
                response = json.dumps(response)

                rds.publish('neo-response', response)

        except ValueError as e:
            print (e)

def main():
    # Setup the blockchain
    blockchain = LevelDBBlockchain(settings.LEVELDB_PATH)
    Blockchain.RegisterBlockchain(blockchain)
    dbloop = task.LoopingCall(Blockchain.Default().PersistBlocks)
    dbloop.start(.1)
    NodeLeader.Instance().Start()

    # Start smart contract thread
    smart_contract.start()

    # Start a thread with listener for remote commands
    d = threading.Thread(target=Listener)
    d.setDaemon(True)
    d.start()

    # Run all the things (blocking call)
    logger.info("Everything setup and running. Waiting for events...")
    reactor.run()
    logger.info("Shutting down.")

if __name__ == "__main__":
    main()
