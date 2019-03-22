class MultiSigDeprecationWitness:
    def __init__(self, next_state_commitment, signatures, inclusion_witness):
        self.next_state_commitment = next_state_commitment
        self.signatures = signatures
        self.inclusion_witness = inclusion_witness

class MultiSigPredicate:
    dispute_duration = 10

    def __init__(self, parent_plasma_contract):
        self.parent = parent_plasma_contract

    def can_initiate_exit(self, commitment, initiation_witness):
        # For now, anyone can submit an exit TODO: make this one or multiple of owners
        return True

    def verify_deprecation(self, state_id, commitment, revocation_witness):
        # Check the state_id is in the commitment
        assert commitment.start <= state_id and commitment.end > state_id
        # Check the state_id is in the revocation_witness commitment
        assert revocation_witness.next_state_commitment.start <= state_id and revocation_witness.next_state_commitment.end > state_id
        # Check inclusion proof
        assert self.parent.commitment_chain.verify_inclusion(revocation_witness.next_state_commitment,
                                                                self.parent.address,
                                                                revocation_witness.inclusion_witness)
        # Check that all owners signed off on the change
        assert commitment.state.recipient == revocation_witness.signatures
        # Check that the spend is after the exit state
        assert commitment.plasma_block_number < revocation_witness.next_state_commitment.plasma_block_number
        return True

    def finalize_exit(self, exit):
        # Extract required information from call data
        recipients_sigs, destination = call_data
        # Check that the resolution is signed off on by all parties in the multisig
        assert recipients_sigs == exit.commitment.state.recipient
        # Transfer funds to the recipient
        self.parent.erc20_contract.transferFrom(self, destination, exit.commitment.end - exit.commitment.start)

    def get_additional_lockup(self, state):
        return 0
