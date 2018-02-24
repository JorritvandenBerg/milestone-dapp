"""
Milestone dApp.

===================================

Milestone is a dApp for virtual collaboration. It allows project managers
to create milestones and assign them for a reward. Project managers can review
deliverables themselves or delegate reviewing to someone else. This smart
contract functions as an escrow for the reward. The project manager deposits
the reward and fee and once the milestone is reviewed positively, the assignee
will receive the pay out.
"""

from boa.blockchain.vm.Neo.Runtime import Notify, GetTrigger, CheckWitness
from boa.blockchain.vm.Neo.Blockchain import GetHeight, GetHeader
from boa.blockchain.vm.Neo.Action import RegisterAction
from boa.blockchain.vm.Neo.TriggerType import Application, Verification
from common.txio import Attachments, get_asset_attachments
from common.serializers import serialize_array, deserialize_bytearray, serialize_var_length_item
from boa.blockchain.vm.Neo.Storage import GetContext, Get, Put, Delete
from boa.code.builtins import list


# -------------------------------------------
# DAPP SETTINGS
# -------------------------------------------

# Script hash of the token owner
OWNER = b'#\xba\'\x03\xc52c\xe8\xd6\xe5"\xdc2 39\xdc\xd8\xee\xe9'

# INITIAL_FEE in asset units (can be adjusted with setFee operation)
INITIAL_FEE = 1

# MIN_TIME in seconds for the milestone to be in the future (1 day default)
MIN_TIME = 86400

# MAX_TIME in seconds for the milestone to be in the future (365 days default)
MAX_TIME = 31536000

# TIME_MARGIN margin for the above constants (1 hour default)
TIME_MARGIN = 3600

# -------------------------------------------
# Events
# -------------------------------------------

DispatchFeeUpdateEvent = RegisterAction('fee')
DispatchMilestoneEvent = RegisterAction('milestone', 'milestone_key')
DispatchReviewEvent = RegisterAction('review', 'milestone_key', 'review_score')
DispatchTransferEvent = RegisterAction('transfer', 'from', 'to', 'amount')
DispatchRefundEvent = RegisterAction('refund', 'milestone_key')
DispatchDeleteMilestoneEvent = RegisterAction('delete', 'milestone_key')


def Main(operation, args):
    """
    This is the main entry point for the dApp
    :param operation: the operation to be performed
    :type operation: str
    :param args: an optional list of arguments
    :type args: list
    :return: indicating the successful execution of the dApp
    :rtype: bool
    """
    trigger = GetTrigger()

    if trigger == Verification():

        # if the script that sent this is the owner
        # we allow the spend
        is_owner = CheckWitness(OWNER)

        if is_owner:

            return True

        return False

    elif trigger == Application():

        if operation == 'name':
            n = 'Milestone'
            return n

        elif operation == 'fee':
            context = GetContext()
            f = Get(context, 'fee')

            if len(f) == 0:
                f = INITIAL_FEE

            return f

        elif operation == 'setFee':
            if len(args) == 1:
                new_fee = args[0]
                context = GetContext()
                Delete(context, 'fee')
                Put(context, 'fee', new_fee)
                DispatchFeeUpdateEvent(new_fee)
                return True
            else:
                return False

        elif operation == 'milestone':
            if len(args) == 11:
                milestone_key = args[0]
                agreement = args[1]
                customer = args[2]
                assignee = args[3]
                platform = args[4]
                timestamp = args[5]
                utc_offset = args[6]
                oracle = args[7]
                pay_out = args[8]
                asset = args[9]
                threshold = args[10]
                a = Milestone(milestone_key, agreement, customer, assignee, platform, timestamp, utc_offset, pay_out, oracle, asset, threshold)

                Notify("Milestone added!")
                return a

            else:
                return False

        elif operation == 'review':
            if len(args) == 2:
                milestone_key = args[0]
                review_score = args[1]
                return Review(milestone_key, review_score)

            else:
                return False

        elif operation == 'transfer':
            if len(args) == 3:
                t_from = args[0]
                t_to = args[1]
                t_amount = args[2]
                return DoTransfer(t_from, t_to, t_amount)

            else:
                return False

        elif operation == 'refund':
            if len(args) == 2:
                milestone_key = args[0]
                fee_refund = args[1]
                return Refund(milestone_key, fee_refund)

            else:
                return False

        elif operation == 'deleteMilestone':
            if len(args) == 1:
                milestone_key = args[0]
                return DeleteMilestone(milestone_key)

            else:
                return False

        result = 'unknown operation'

        return result

    return False


def Milestone(milestone_key, agreement, customer, assignee, platform,
              timestamp, utc_offset, oracle, pay_out, asset, threshold):
    """
    Method to create a milestone

    :param milestone_key: unique identifier for the milestone
    :type milestone_key: str

    :param agreement: key of the parent agreement this milestone belongs to
    :type agreement: str

    :param customer: customer party of the milestone
    :type customer: bytearray

    :param assignee: assignee party of the milestone
    :type assignee: bytearray

    :platform: id of platform on which the project repository is (e.g. GitHub)
    :type platform: str

    :param timestamp: timezone naive datetime of the day of the event
    :type timestamp: int

    :param utc_offset: positive or negative utc_offset for timestamp
    :type utc_offset: int

    :param oracle: oracle (reviewer of the task)
    :type oracle: bytearray

    :param pay_out: the amount to pay out to the assignee on success
    :type pay_out: int

    :param asset: the NEO asset used in the milestone instance
    type asset: bytearray

    :param threshold: the minimum score for the milestone (out of 100)
    :type threshold: int

    :return: whether the milestone was successfully added
    :rtype: bool
    """

    context = GetContext()
    m = Get(context, milestone_key)

    if len(m) > 0:
        Notify("milestone_key not unique, please use another")
        return False

    # Get timestamp of current block
    currentHeight = GetHeight()
    currentBlock = GetHeader(currentHeight)
    current_time = currentBlock.Timestamp

    # Compute timezone adjusted time
    timezone_timestamp = timestamp + (utc_offset * 3600)
    timezone_current_time = current_time + (utc_offset * 3600)

    # Check if timestamp is not out of boundaries
    if timezone_timestamp < (timezone_current_time + MIN_TIME - TIME_MARGIN):
        Notify("Datetime must be $MIN_TIME seconds ahead")
        return False

    elif timezone_timestamp > (timezone_current_time + MAX_TIME + TIME_MARGIN):
        Notify("Datetime must be $MAX_TIME seconds ahead")
        return False

    fee = Get(context, 'fee')

    if len(fee) == 0:
        fee = INITIAL_FEE

    # Check if pay_out and fee are not zero or below
    if pay_out <= 0:
        Notify("Pay_out is zero or negative")
        return False

    if fee <= 0:
        Notify("Fee is zero or negative")
        return False

    # check if payment is received if milestone is not created by OWNER
    if not CheckWitness(OWNER):
        attachments = get_asset_attachments()
        total_cost = pay_out + fee

        if asset == attachments.neo_asset_id:
            if attachments.neo_attached > 0:
                if not attachments.neo_attached == total_cost:
                    Notify("Incorrect payment received, returning funds")
                    DoTransfer(OWNER, customer, attachments.neo_attached)
                    return False
            else:
                Notify("No payment received")
                return False

        elif asset == attachments.gas_asset_id:
            if attachments.gas_attached > 0:
                if not attachments.gas_attached == total_cost:
                    Notify("Incorrect payment received, returning funds")
                    DoTransfer(OWNER, customer, attachments.gas_attached)
                    return False
            else:
                Notify("No payment received")
                return False

    status = 'initialized'

    # Set place holder value
    review_score = 0

    milestone_data = [agreement, customer, assignee, platform, timestamp, utc_offset, oracle, pay_out, asset, fee, threshold, status, review_score]
    milestone_data_serialized = serialize_array(milestone_data)
    Put(context, milestone_key, milestone_data_serialized)

    DispatchMilestoneEvent(milestone_key)

    return True


def Review(milestone_key, review_score):
    """
    Method to signal result by SC owner or oracle

    :param milestone_key: the key of the milestone
    :type milestone_key: bytearray

    :param review_score: score that the reviewer assigned to this milestone
    :type review_score: int

    :return: whether a pay out to the assignee is done
    :rtype: bool
    """
    # Check if the method is triggered by the SC owner or oracle
    context = GetContext()
    milestone_data_serialized = Get(context, milestone_key)
    milestone_data = deserialize_bytearray(milestone_data_serialized)
    oracle = milestone_data[6]

    if not CheckWitness(OWNER) and not CheckWitness(oracle):
        Notify("Must be SC owner or oracle to submit review")
        return False

    status = milestone_data[11]

    if not status == 'initialized':
        Notify("Contract has incorrect status to do a review")
        return False

    elif status == 'refunded':
        Notify("Contract is already refunded")
        return False

    milestone_data[11] = 'reviewed'
    milestone_data[12] = review_score
    assignee = milestone_data[2]
    threshold = milestone_data[10]
    pay_out = milestone_data[7]

    # Update storage
    Delete(context, milestone_key)
    milestone_data_serialized = serialize_array(milestone_data)
    Put(context, milestone_key, milestone_data_serialized)
    DispatchReviewEvent(milestone_key, review_score)

    if review_score >= threshold:
        Notify("Review score was above threshold, processing pay out")
        DoTransfer(OWNER, assignee, pay_out)
        DispatchTransferEvent(OWNER, assignee, pay_out)

    return True


def DoTransfer(sender, receiver, amount):
    """
    Method to transfer tokens from one account to another

    :param sender: the address to transfer from
    :type sender: bytearray

    :param receiver: the address to transfer to
    :type receiver: bytearray

    :param amount: the amount of tokens to transfer
    :type amount: int

    :return: whether the transfer was successful
    :rtype: bool

    """
    if amount <= 0:
        Notify("Cannot transfer negative amount")
        return False

    from_is_sender = CheckWitness(sender)

    if not from_is_sender:
        Notify("Not owner of funds to be transferred")
        return False

    if sender == receiver:
        Notify("Sending funds to self")
        return True

    context = GetContext()
    from_val = Get(context, sender)

    if from_val < amount:
        Notify("Insufficient funds to transfer")
        return False

    if from_val == amount:
        Delete(context, sender)

    else:
        difference = from_val - amount
        Put(context, sender, difference)

    to_value = Get(context, receiver)

    to_total = to_value + amount

    Put(context, receiver, to_total)
    DispatchTransferEvent(sender, receiver, amount)

    return True


def Refund(milestone_key, fee_refund):
    """
    Method for the contract owner to refund payments

    :param milestone_key: milestone_key
    :type milestone_key: bytearray

    :param fee_refund: fee_refund
    :type fee_refund: bool

    :return: whether the refund was successful
    :rtype: bool

    """
    if not CheckWitness(OWNER):
        Notify("Must be owner to do a refund to all")
        return False

    context = GetContext()
    milestone_data_serialized = Get(context, milestone_key)
    milestone_data = deserialize_bytearray(milestone_data_serialized)
    customer = milestone_data[1]
    status = milestone_data[11]
    pay_out = milestone_data[7]
    fee = milestone_data[9]

    if status == 'refunded':
        Notify("A refund already took place")
        return False

    # Perform refund
    if fee_refund:
        refund_amount = pay_out + fee
    else:
        refund_amount = pay_out

    DoTransfer(OWNER, customer, refund_amount)
    DispatchTransferEvent(OWNER, customer, refund_amount)

    milestone_data[11] = 'refunded'
    milestone_data_serialized = serialize_array(milestone_data)
    Delete(context, milestone_key)
    Put(context, milestone_key, milestone_data_serialized)
    DispatchRefundEvent(milestone_key)

    return True


def DeleteMilestone(milestone_key):
    """
    Method for the dApp owner to delete claimed or refunded agreements

    :param milestone_key: milestone_key
    :type milestone_key: str

    :return: whether the deletion succeeded
    :rtype: bool
    """
    if not CheckWitness(OWNER):
        Notify("Must be owner to delete an agreement")
        return False

    context = GetContext
    milestone_data_serialized = Get(context, milestone_key)
    milestone_data = deserialize_bytearray(milestone_data_serialized)
    status = milestone_data[11]

    if status == 'reviewed':
        Delete(context, milestone_key)
        DispatchDeleteMilestoneEvent(milestone_key)
        return True

    elif status == 'refunded':
        Delete(context, milestone_key)
        DispatchDeleteMilestoneEvent(milestone_key)
        return True

    return False
