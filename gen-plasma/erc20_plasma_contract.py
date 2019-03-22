from utils import State, Exit, StateUpdate, Challenge

class exitableRange:
    def __init__(self, start, is_set):
        self.start = start

class Erc20PlasmaContract:
    def __init__(self, eth, address, erc20_contract, state_update_chain, DISPUTE_PERIOD):
        # Settings
        self.eth = eth
        self.address = address
        self.erc20_contract = erc20_contract
        self.state_update_chain = state_update_chain
        self.DISPUTE_PERIOD = DISPUTE_PERIOD
        # Datastructures
        self.total_deposited = 0
        self.exitable_ranges = dict()
        self.deposits = dict()
        self.exits = []
        self.challenges = []

    def deposit(self, depositor, deposit_amount, predicate, parameters):
        assert deposit_amount > 0
        # Make the transfer
        self.erc20_contract.transferFrom(depositor, self.address, deposit_amount)
        # Record the deposit first by collecting the preceeding plasma block number
        preceding_plasma_block_number = len(self.state_update_chain.blocks) - 1
        # Next compute the start and end positions of the deposit
        deposit_start = self.total_deposited
        deposit_end = self.total_deposited + deposit_amount
        # Create the initial state which we will record to in this deposit
        initial_state = State(predicate, parameters)
        # Create the depoisit object
        deposit = StateUpdate(initial_state, deposit_start, deposit_end, preceding_plasma_block_number)
        # Store the deposit in case it needs to be exited
        self.deposits[deposit_end] = deposit # technically this dupes the deposit_end as it stands now, so TODO: make deposits not exactly state Updates
        #  Update our mapping of ranges which can be exited
        self.exitable_ranges[deposit_end] = deposit_start # TODO: if there's a exitable range ending at deposit_end already, extend that instead of creating a new one.
        # Increment total deposits
        self.total_deposited = deposit_end
        # Return deposit record
        return deposit

    def _construct_exit(self, state_update):
        additional_lockup_duration = state_update.state.predicate.get_additional_lockup(state_update.state)
        eth_block_redeemable = self.eth.block_number + self.DISPUTE_PERIOD + additional_lockup_duration
        return Exit(state_update, eth_block_redeemable)

    def exit_deposit(self, deposit_end):
        deposit = self.deposits[deposit_end]
        exit = self._construct_exit(deposit)
        self.exits.append(exit)
        return len(self.exits) - 1

    def exit_state_update(self, state_update, state_update_witness, exitability_witness):
        assert self.state_update_chain.verify_inclusion(state_update, self.address, state_update_witness)
        assert state_update.state.predicate.can_initiate_exit(state_update, exitability_witness)
        exit = self._construct_exit(state_update)
        self.exits.append(exit)
        return len(self.exits) - 1

    def challenge_deprecated_exit(self, state_id, exit_id, revocation_witness):
        exit = self.exits[exit_id]
        # Call can revoke to check if the predicate allows this revocation attempt
        assert exit.state_update.state.predicate.verify_deprecation(state_id, exit.state_update, revocation_witness)
        # Delete the exit
        self.exits[exit_id].is_revoked = True

    def remove_challenge(self, challenge_id):
        challenge = self.challenges[challenge_id]
        earlier_exit = self.exits[challenge.earlier_exit_id]
        assert earlier_exit.is_revoked
        # All checks have passed, we have an earlier exit that was revoked and the challenge is no longer valid.
        # Decrement the challenge count on the later exit
        self.exits[challenge.later_exit_id].num_challenges -= 1
        # Delete the challenge
        del self.challenges[challenge_id]

    def challenge_exit(self, earlier_exit_id, later_exit_id):
        earlier_exit = self.exits[earlier_exit_id]
        later_exit = self.exits[later_exit_id]
        # Make sure they overlap
        assert earlier_exit.state_update.start <= later_exit.state_update.end
        assert later_exit.state_update.start <= earlier_exit.state_update.end
        # Validate that the earlier exit is in fact earlier
        assert earlier_exit.state_update.plasma_block_number < later_exit.state_update.plasma_block_number
        # Make sure the later exit isn't already redeemable
        assert self.eth.block_number < later_exit.eth_block_redeemable
        # Create and record our new challenge
        new_challenge = Challenge(earlier_exit_id, later_exit_id)
        self.challenges.append(new_challenge)
        later_exit.num_challenges += 1
        # If the `eth_block_redeemable` of the earlier exit is longer than later exit, extend the later exit dispute period
        if later_exit.eth_block_redeemable < earlier_exit.eth_block_redeemable:
            later_exit.eth_block_redeemable = earlier_exit.eth_block_redeemable
        # Return our new challenge object
        return len(self.challenges) - 1

    def finalize_exit(self, exit_id, exitable_range_end):
        exit = self.exits[exit_id]
        # Check the exit's eth_block_redeemable has passed
        assert exit.eth_block_redeemable <= self.eth.block_number
        # Check that there are no open challenges for the exit
        assert exit.num_challenges == 0
        # Make sure that the exitable_range_end is actually in exitable_ranges
        assert exitable_range_end in self.exitable_ranges
        # Make sure the exit is within the exitable range
        assert exit.state_update.start >= self.exitable_ranges[exitable_range_end]
        assert exit.state_update.end <= exitable_range_end
        # Update exitable range
        # TODO: delete if these are both equal?
        if exit.state_update.start != self.exitable_ranges[exitable_range_end]:
            self.exitable_ranges[exit.state_update.start] = self.exitable_ranges[exitable_range_end]
        if exit.state_update.end != exitable_range_end:
            self.exitable_ranges[exitable_range_end] = exit.state_update.end
        # Approve coins for spending in predicate
        self.erc20_contract.approve(self.address, exit.state_update.state.predicate, exit.state_update.end - exit.state_update.start)
        # Finally redeem the exit
        exit.state_update.state.predicate.finalize_exit(exit)
