from utils import State, StateUpdate
from predicates.ownership import OwnershipDeprecationWitness

def test_submit_exit_on_deposit(alice, erc20_plasma_ct, ownership_predicate):
    commit0_alice_deposit = erc20_plasma_ct.deposit(alice.address, 100, ownership_predicate, {'owner': alice.address})
    # Try submitting exit
    erc20_plasma_ct.exit_deposit(commit0_alice_deposit.end)
    # Check the exit was recorded
    assert len(erc20_plasma_ct.exits) == 1

def test_submit_exit_on_commitment(alice, bob, operator, erc20_plasma_ct, ownership_predicate):
    # Deposit and send a tx
    commit0_alice_deposit = erc20_plasma_ct.deposit(alice.address, 100, ownership_predicate, {'owner': alice.address})  # Add deposit
    state_bob_ownership = State(ownership_predicate, {'owner': bob.address})
    commit1_alice_to_bob = StateUpdate(state_bob_ownership, commit0_alice_deposit.start, commit0_alice_deposit.end, 0)  # Create commitment
    # Add the commit
    erc20_plasma_ct.commitment_chain.commit_block(operator.address, {erc20_plasma_ct.address: [commit1_alice_to_bob]})
    # Try submitting exit
    exit_id = erc20_plasma_ct.exit_commitment(commit1_alice_to_bob, 'merkle proof', bob.address)
    # Check the exit was recorded
    assert len(erc20_plasma_ct.exits) == 1
    # Now increment the eth block to the redeemable block
    erc20_plasma_ct.eth.block_number = erc20_plasma_ct.exits[exit_id].eth_block_redeemable
    # Finally try withdrawing the money!
    erc20_plasma_ct.redeem_exit(exit_id, commit1_alice_to_bob.end)
    # Check bob's balance!
    assert erc20_plasma_ct.erc20_contract.balanceOf(bob.address) == 1100  # 1100 comes from bob having been sent 100 & already having 1000

def test_revoke_exit_on_deposit(alice, bob, operator, erc20_plasma_ct, ownership_predicate):
    # Deposit and send a tx
    commit0_alice_deposit = erc20_plasma_ct.deposit(alice.address, 100, ownership_predicate, {'owner': alice.address})  # Add deposit
    state_bob_ownership = State(ownership_predicate, {'owner': bob.address})
    commit1_alice_to_bob = StateUpdate(state_bob_ownership, commit0_alice_deposit.start, commit0_alice_deposit.end, 0)  # Create commitment
    # Add the commitment
    erc20_plasma_ct.commitment_chain.commit_block(operator.address, {erc20_plasma_ct.address: [commit1_alice_to_bob]})
    deprecation_witness0_alice_to_bob = OwnershipDeprecationWitness(commit1_alice_to_bob, alice.address, 'merkle proof')
    # Try submitting exit on deposit
    deposit_exit_id = erc20_plasma_ct.exit_deposit(100)
    # Check the exit was recorded
    assert len(erc20_plasma_ct.exits) == 1
    # Now bob revokes the exit with the spend inside the revocation witness
    erc20_plasma_ct.revoke_exit(10, deposit_exit_id, deprecation_witness0_alice_to_bob)
    # Check the exit was revoked
    assert erc20_plasma_ct.exits[deposit_exit_id].is_revoked

def test_challenge_exit_with_invalid_state(alice, mallory, operator, erc20_plasma_ct, ownership_predicate):
    # Deposit and commit to invalid state
    commit0_alice_deposit = erc20_plasma_ct.deposit(alice.address, 100, ownership_predicate, {'owner': alice.address})  # Add deposit
    # Check that alice's balance was reduced
    assert erc20_plasma_ct.erc20_contract.balanceOf(alice.address) == 900
    # Uh oh! Malory creates an invalid state & commits it!!!
    state_mallory_ownership = State(ownership_predicate, {'owner': mallory.address})
    invalid_commit1_alice_to_mallory = StateUpdate(state_mallory_ownership,
                                                  commit0_alice_deposit.start,
                                                  commit0_alice_deposit.end,
                                                  0)  # Create commitment
    # Add the commitment
    erc20_plasma_ct.commitment_chain.commit_block(operator.address, {erc20_plasma_ct.address: [invalid_commit1_alice_to_mallory]})
    # Submit a exit for the invalid state
    invalid_commitment_exit_id = erc20_plasma_ct.exit_commitment(invalid_commit1_alice_to_mallory, 'merkle proof', mallory.address)
    # Oh no! Alice notices bad behavior and attempts withdrawal of deposit state
    deposit_exit_id = erc20_plasma_ct.exit_deposit(commit0_alice_deposit.end)
    # Alice isn't letting that other exit go through. She challenges it with her deposit!
    challenge = erc20_plasma_ct.challenge_exit(deposit_exit_id, invalid_commitment_exit_id)
    # Verify that the challenge was recorded
    assert challenge is not None and len(erc20_plasma_ct.challenges) == 1
    # Fast forward in time until the eth block allows the exit to be redeemable
    erc20_plasma_ct.eth.block_number = erc20_plasma_ct.exits[invalid_commitment_exit_id].eth_block_redeemable
    # Mallory attempts and fails to withdraw because there's another exit with priority
    try:
        erc20_plasma_ct.redeem_exit(mallory.address, invalid_commit1_alice_to_mallory.end)
        throws = False
    except Exception:
        throws = True
    assert throws
    # Now instead alice withdraws
    erc20_plasma_ct.redeem_exit(deposit_exit_id, erc20_plasma_ct.exits[deposit_exit_id].state_update.end)
    # Check that alice was sent her money!
    assert erc20_plasma_ct.erc20_contract.balanceOf(alice.address) == 1000

def test_redeem_challenged_exit(alice, mallory, operator, erc20_plasma_ct, ownership_predicate):
    # Deposit and then submit an invalid challenge
    commit0_mallory_deposit = erc20_plasma_ct.deposit(mallory.address, 100, ownership_predicate, {'owner': mallory.address})  # Add deposit
    # Create a new state & commitment for alice ownership
    state_alice_ownership = State(ownership_predicate, {'owner': alice.address})
    commit1_mallory_to_alice = StateUpdate(state_alice_ownership, commit0_mallory_deposit.start, commit0_mallory_deposit.end, 0)  # Create commitment
    # Add the commit
    erc20_plasma_ct.commitment_chain.commit_block(operator.address, {erc20_plasma_ct.address: [commit1_mallory_to_alice]})
    # Now alice wants to withdraw, so submit a new exit on the funds
    exit_id = erc20_plasma_ct.exit_commitment(commit1_mallory_to_alice, 'merkle proof', alice.address)
    # Uh oh! Mallory decides to withdraw and challenge the exit
    revoked_exit_id = erc20_plasma_ct.exit_deposit(commit0_mallory_deposit.end)
    challenge_id = erc20_plasma_ct.challenge_exit(revoked_exit_id, exit_id)
    # This revoked exit is then swiftly canceled by alice
    deprecation_witness0_mallory_to_alice = OwnershipDeprecationWitness(commit1_mallory_to_alice, mallory.address, 'merkle proof')
    erc20_plasma_ct.revoke_exit(10, revoked_exit_id, deprecation_witness0_mallory_to_alice)
    # Remove the challenge for the revoked exit
    erc20_plasma_ct.remove_challenge(challenge_id)
    # Increment the eth block number
    erc20_plasma_ct.eth.block_number = erc20_plasma_ct.exits[exit_id].eth_block_redeemable
    # Now alice can withdraw!
    erc20_plasma_ct.redeem_exit(exit_id, erc20_plasma_ct.exits[exit_id].state_update.end)
    # Check that alice was sent her money!
    assert erc20_plasma_ct.erc20_contract.balanceOf(alice.address) == 1100
