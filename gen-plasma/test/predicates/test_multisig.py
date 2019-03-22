import pytest
from utils import State
from predicates.multisig import MultiSigDeprecationWitness, MultiSigPredicate

@pytest.fixture
def multisig_predicate(erc20_plasma_ct):
    return MultiSigPredicate(erc20_plasma_ct)

def skip_test_submit_exit_on_deposit(alice, bob, charlie, erc20_plasma_ct, multisig_predicate):
    state0_alice_and_bob_deposit = erc20_plasma_ct.deposit_ERC20(alice.address,
                                                                 100,
                                                                 multisig_predicate,
                                                                 {'recipient': [alice.address, bob.address]})
    # Try submitting exit
    erc20_plasma_ct.submit_exit(state0_alice_and_bob_deposit)
    # Check the exit was recorded
    assert len(erc20_plasma_ct.exit_queues) == 1

def skip_test_submit_exit_on_transaction(alice, bob, charlie, erc20_plasma_ct, multisig_predicate):
    # Deposit and send a tx
    state0_alice_and_bob_deposit = erc20_plasma_ct.deposit_ERC20(alice.address,
                                                                 100,
                                                                 multisig_predicate,
                                                                 {'recipient': [alice.address, bob.address]})
    state1_alice_and_bob = State(state0_alice_and_bob_deposit.coin_id,
                                 0,
                                 multisig_predicate,
                                 {'recipient': [charlie.address]})
    erc20_plasma_ct.add_state_update([state1_alice_and_bob])  # Add the tx to the first state_update
    # Try submitting exit
    erc20_plasma_ct.submit_exit(state1_alice_and_bob, 0)
    # Check the exit was recorded
    assert len(erc20_plasma_ct.exit_queues) == 1

def skip_test_submit_dispute_on_deposit(alice, bob, charlie, erc20_plasma_ct, multisig_predicate):
    # Deposit and send a tx
    state0_alice_and_bob_deposit = erc20_plasma_ct.deposit_ERC20(alice.address,
                                                                 100,
                                                                 multisig_predicate,
                                                                 {'recipient': [alice.address, bob.address]})
    state1_alice_and_bob = State(state0_alice_and_bob_deposit.coin_id,
                                 0,
                                 multisig_predicate,
                                 {'recipient': [charlie.address]})
    erc20_plasma_ct.add_state_update([state1_alice_and_bob])  # Add the tx to the first state_update
    # Create witness based on this state_update
    transition_witness0_alice_and_bob = MultiSigTransitionWitness([alice.address, bob.address], 0)
    # Try submitting exit on deposit
    deposit_exit = erc20_plasma_ct.submit_exit(state0_alice_and_bob_deposit)
    # Check the exit was recorded
    assert len(erc20_plasma_ct.exit_queues[state1_alice_and_bob.coin_id]) == 1
    # Now bob disputes exit with the spend
    erc20_plasma_ct.dispute_exit(bob.address, deposit_exit, transition_witness0_alice_and_bob, state1_alice_and_bob)
    # Check the exit was deleted
    assert len(erc20_plasma_ct.exit_queues[state1_alice_and_bob.coin_id]) == 0

def skip_test_invalid_tx_exit_queue_resolution(alice, bob, mallory, erc20_plasma_ct, multisig_predicate, erc20_ct):
    # Deposit and commit to an invalid state
    state0_alice_and_bob_deposit = erc20_plasma_ct.deposit_ERC20(alice.address,
                                                                 100,
                                                                 multisig_predicate,
                                                                 {'recipient': [alice.address, bob.address]})
    state1_mallory_to_mallory = State(state0_alice_and_bob_deposit.coin_id,
                                      0,
                                      multisig_predicate,
                                      {'recipient': [mallory.address]})
    erc20_plasma_ct.add_state_update([state1_mallory_to_mallory])  # Add the invalid tx to the first state_update
    # Submit a exit for the invalid state
    invalid_exit = erc20_plasma_ct.submit_exit(state1_mallory_to_mallory, 0)
    # Alice notices the invalid exit, and submits her own exit. Note that it is based on her deposit which is before the tx
    valid_exit = erc20_plasma_ct.submit_exit(state0_alice_and_bob_deposit)
    # Wait for the dispute period to end.
    erc20_plasma_ct.eth.block_number += multisig_predicate.dispute_duration
    # Mallory attempts and fails to withdraw because there's another exit with priority
    try:
        erc20_plasma_ct.resolve_exit(mallory.address, invalid_exit)
        throws = False
    except Exception:
        throws = True
    assert throws
    # Now alice and bob agree to send the money to a new on-chain multisig
    erc20_plasma_ct.resolve_exit(alice.address, valid_exit, ([alice.address, bob.address], 'on chain multisig address'))
    # Check that the balances have updated
    assert erc20_ct.balanceOf('on chain multisig address') == 100
    assert erc20_ct.balanceOf(erc20_plasma_ct.address) == 0
