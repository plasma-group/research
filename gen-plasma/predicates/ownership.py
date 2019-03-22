class OwnershipDeprecationWitness:
    def __init__(self, next_state_update, signature, inclusion_witness):
        self.next_state_update = next_state_update
        self.signature = signature
        self.inclusion_witness = inclusion_witness

class OwnershipPredicate:

    def __init__(self, parent_plasma_contract):
        self.parent = parent_plasma_contract

    def can_initiate_exit(self, state_update, initiation_witness):
        # Only the owner can submit a claim
        assert state_update.state.owner == initiation_witness
        return True

    def verify_deprecation(self, state_id, state_update, deprecation_witness):
        # Check the state_id is in the deprecation_witness state update
        assert deprecation_witness.next_state_update.start <= state_id and deprecation_witness.next_state_update.end > state_id
        # Check inclusion proof for more recent state update
        assert self.parent.commitment_chain.verify_inclusion(deprecation_witness.next_state_update,
                                                                self.parent.address,
                                                                deprecation_witness.inclusion_witness)
        # Check that the previous owner signed off on the change
        assert state_update.state.owner == deprecation_witness.signature
        return True

    def finalize_exit(self, exit):
        # Transfer funds to the owner
        self.parent.erc20_contract.transferFrom(self, exit.state_update.state.owner, exit.state_update.end - exit.state_update.start)

    def get_additional_lockup(self, state):
        return 0
