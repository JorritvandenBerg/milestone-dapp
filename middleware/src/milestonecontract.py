import time
import threading

from queue import Queue
from redis import Redis
from logzero import logger
from twisted.internet import task

from neo.Implementations.Wallets.peewee.UserWallet import UserWallet
from neo.Prompt.Commands.Invoke import InvokeContract, TestInvokeContract, test_invoke
from neo.Settings import settings
from neo.Core.Blockchain import Blockchain

from contrib.smartcontract import SmartContract

# Setup the blockchain task queue
class MilestoneSmartContract(threading.Thread):
    """
    Invoke queue is necessary for handling many concurrent sc invokes.

    Eg. many api calls want to initiate a smart contract methods, they add them
    to this queue, and they get processed as they can (eg. if gas is available)
    """
    smart_contract = None
    contract_hash = None

    wallet_path = None
    wallet_pass = None

    tx_in_progress = None

    invoke_queue = None  # Queue items are always a tuple (method_name, args)
    wallet = None
    _walletdb_loop = None

    def __init__(self, contract_hash, wallet_path, wallet_pass):
        super(MilestoneSmartContract, self).__init__()
        self.daemon = True

        self.contract_hash = contract_hash
        self.wallet_path = wallet_path
        self.wallet_pass = wallet_pass

        self.smart_contract = SmartContract(contract_hash)
        self.invoke_queue = Queue()

        # Setup redis
        self.rds = Redis(host='localhost', port=6379, db=0)

        self.tx_in_progress = None
        self.wallet = None

        settings.set_log_smart_contract_events(False)

        # Setup handler for smart contract Runtime.Notify event
        #
        @self.smart_contract.on_notify
        def sc_notify(event):
            """ This method catches Runtime.Notify calls, and add them to Redis """
            logger.info("sc_notify event: %s", str(event))

            # Make sure that the event payload list has at least one element.
            if not len(event.event_payload):
                return

            # The event payload list has at least one element. As developer of the smart contract
            # you should know what data-type is in the bytes, and how to decode it. In this example,
            # it's just a string, so we decode it with utf-8:
            msg = event.event_payload[0].decode("utf-8")
            self.rds.publish('neo-event', msg)

    def add_invoke(self, method_name, *args):
        logger.info("SmartContractInvokeQueue add_invoke %s %s" % (method_name, str(args)))
        logger.info("- queue size: %s", self.invoke_queue.qsize())
        self.invoke_queue.put((method_name, args))

    def run(self):
        while True:
            task = self.invoke_queue.get()
            logger.info("SmartContractInvokeQueue Task: %s", str(task))
            method_name, args = task
            logger.info("- method_name: %s, args: %s", method_name, task)
            logger.info("- queue size: %s", self.invoke_queue.qsize())

            try:
                self.invoke_method(method_name, *args)

            except Exception as e:
                logger.exception(e)

                # Wait a few seconds
                logger.info("wait 60 seconds...")
                time.sleep(60)

                # Re-add the task to the queue
                logger.info("Re-adding task to queue")
                self.invoke_queue.put(task)

            finally:
                # Always mark task as done, because even on error it was done and re-added
                self.invoke_queue.task_done()

    def open_wallet(self):
        """ Open a wallet. Needed for invoking contract methods. """
        assert self.wallet is None
        self.wallet = UserWallet.Open(self.wallet_path, self.wallet_pass)
        self._walletdb_loop = task.LoopingCall(self.wallet.ProcessBlocks)
        self._walletdb_loop.start(1)

    def close_wallet(self):
        self._walletdb_loop.stop()
        self._walletdb_loop = None
        self.wallet = None

    def wallet_has_gas(self):
        # Make sure no tx is in progress and we have GAS
        synced_balances = self.wallet.GetSyncedBalances()
        for balance in synced_balances:
            asset, amount = balance
            logger.info("- balance %s: %s", asset, amount)
            if asset == "NEOGas" and amount > 0:
                return True

        return False

    def _wait_for_tx(self, tx, max_seconds=300):
        """ Wait for tx to show up on blockchain """
        sec_passed = 0
        while sec_passed < max_seconds:
            _tx, height = Blockchain.Default().GetTransaction(tx.Hash.ToString())
            if height > -1:
                return True
            # logger.info("Waiting for tx {} to show up on blockchain...".format(tx.Hash.ToString()))
            time.sleep(5)
            sec_passed += 5

        logger.error("Transaction was relayed but never accepted by consensus node")
        return False

    def invoke_method(self, method_name, *args):
        """ invoke a method of the smart contract """

        logger.info("invoke_method: method_name=%s, args=%s", method_name, args)
        logger.info("Block %s / %s" % (str(Blockchain.Default().Height), str(Blockchain.Default().HeaderHeight)))

        self.open_wallet()

        if not self.wallet:
            raise Exception("Open a wallet before invoking a smart contract method.")

        if self.tx_in_progress:
            raise Exception("Transaction already in progress (%s)" % self.tx_in_progress.Hash.ToString())

        logger.info("making sure wallet is synced...")
        time.sleep(3)

        # Wait until wallet is synced:
        while True:
            percent_synced = int(100 * self.wallet._current_height / Blockchain.Default().Height)
            if percent_synced > 99:
                break
            logger.info("waiting for wallet sync... height: %s. percent synced: %s" % (self.wallet._current_height, percent_synced))
            time.sleep(5)

        time.sleep(3)
        logger.info("wallet synced. checking if gas is available...")

        if not self.wallet_has_gas():
            raise Exception("Wallet has no gas.")

        _args = [self.contract_hash, method_name, str(list(args))]
        logger.info("TestInvokeContract args: %s", _args)
        tx, fee, results, num_ops = TestInvokeContract(self.wallet, _args)
        if not tx:
            raise Exception("TestInvokeContract failed")

        logger.info("TestInvokeContract done, calling InvokeContract now...")
        sent_tx = InvokeContract(self.wallet, tx, fee)

        if sent_tx:
            logger.info("InvokeContract success, transaction underway: %s" % sent_tx.Hash.ToString())
            self.tx_in_progress = sent_tx

            found = self._wait_for_tx(sent_tx)
            if found:
                logger.info("✅ tansaction found! all done!")
            else:
                logger.error("=== TX not found!")

            self.close_wallet()

            self.tx_in_progress = None
            logger.info("InvokeContract done, tx_in_progress freed.")

        else:
            raise Exception("InvokeContract failed")
