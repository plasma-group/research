''' state_update Block Structure
{
    subject_0: [state_update_0, state_update_1,...state_update_n],
    subject_1: [state_update_0, state_update_1,...state_update_n],
    ...
    subject_n: [state_update_0, state_update_1,...state_update_n]
}
'''

class CommitmentChainContract:
    def __init__(self, operator):
        self.operator = operator
        self.blocks = []

    def commit_block(self, msg_sender, block):
        assert msg_sender == self.operator
        self.blocks.append(block)

    def verify_inclusion(self, state_update, subject, committment_witness):
        # Note that we are not providing merkle proofs and are instead faking it by storing the full blocks.
        block = self.blocks[state_update.plasma_block_number]
        # Make sure the subject contract address is in fact included in the block.
        # NOTE: We are mocking the inclusion & so we don't actually use the state_update witness.
        assert subject in block
        # Return whether or not this state_update was included
        return state_update in block[subject]
