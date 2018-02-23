import time

from collections import defaultdict
from functools import wraps

from neo.EventHub import events, SmartContractEvent


class SmartContract:

    contract_hash = None
    event_handlers = defaultdict(list)

    def __init__(self, contract_hash):
        assert contract_hash
        self.contract_hash = str(contract_hash)

        # Register EventHub.events handlers to forward for SmartContract decorators
        @events.on(SmartContractEvent.RUNTIME_NOTIFY)
        @events.on(SmartContractEvent.RUNTIME_LOG)
        @events.on(SmartContractEvent.EXECUTION_SUCCESS)
        @events.on(SmartContractEvent.EXECUTION_FAIL)
        @events.on(SmartContractEvent.STORAGE)
        def call_on_event(sc_event):
            # Make sure this event is for this specific smart contract
            if str(sc_event.contract_hash) != self.contract_hash:
                return

            # call event handlers
            handlers = set(self.event_handlers["*"] + self.event_handlers[sc_event.event_type])  # set(..) removes duplicates
            [event_handler(sc_event) for event_handler in handlers]

    def on_any(self, func):
        """ @on_any decorator: calls method on any event for this smart contract """
        return self._add_decorator("*", func)

    def on_notify(self, func):
        """ @on_notify decorator: calls method on Runtime.Notify events """
        return self._add_decorator(SmartContractEvent.RUNTIME_NOTIFY, func)

    def on_log(self, func):
        """ @on_log decorator: calls method on Runtime.Log events """
        # Append function to handler list
        return self._add_decorator(SmartContractEvent.RUNTIME_LOG, func)

    def on_storage(self, func):
        """ @on_storage decorator: calls method on Neo.Storage.* events """
        # Append function to handler list
        return self._add_decorator(SmartContractEvent.STORAGE, func)

    def _add_decorator(self, event_type, func):
        # First, add handler function to handlers
        self.event_handlers[event_type].append(func)

        # Return the wrapper
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
