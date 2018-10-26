
operator: public(address)
deposits: public(wei_value[address])
total_deposits: public(wei_value)
plasma_block_number: public(uint256)
last_publish: public(uint256) # ethereum block number of most recent plasma block
hash_chain: public(bytes32[uint256])
exits: public(
{
    owner: address,
    plasma_block: uint256,
    eth_block: uint256,
    start: uint256,
    offset: uint256,
    challenge_count: uint256,
}[uint256])
challenges: public(
{
    exit_id: uint256,
    ongoing: bool,
    token_id: uint256,
}[uint256])
exit_nonce: public(uint256)
challenge_nonce: public(uint256)

# period (of ethereum blocks) during which an exit can be challenged
CHALLENGE_PERIOD: constant(uint256) = 20
# minimum number of ethereum blocks between new plasma blocks
PLASMA_BLOCK_INTERVAL: constant(uint256) = 10
#
MAX_TREE_DEPTH: constant(uint256) = 8

@public
def __init__():
    self.operator = msg.sender
    self.total_deposits = 0
    self.plasma_block_number = 0
    self.exit_nonce = 0
    self.last_publish = 0
    self.challenge_nonce = 0

@public
@payable
def deposit():
    self.deposits[msg.sender] += msg.value
    self.total_deposits += msg.value

@public
def publish_hash(block_hash: bytes32):
    assert msg.sender == self.operator
    assert block.number >= self.last_publish + PLASMA_BLOCK_INTERVAL

    self.hash_chain[self.plasma_block_number] = block_hash
    self.plasma_block_number += 1
    self.last_publish = block.number

@public
def submit_exit(bn: uint256, start: uint256, offset: uint256) -> uint256:
    assert bn <= self.plasma_block_number
    assert offset > 0
    assert offset < as_unitless_number(self.total_deposits)

    self.exits[self.exit_nonce].owner = msg.sender
    self.exits[self.exit_nonce].plasma_block = bn
    self.exits[self.exit_nonce].eth_block = block.number
    self.exits[self.exit_nonce].start = start
    self.exits[self.exit_nonce].offset = offset
    self.exits[self.exit_nonce].challenge_count = 0

    exit_id : uint256 = self.exit_nonce
    self.exit_nonce += 1
    return exit_id

@public
def finalize_exit(exit_id: uint256):
    assert block.number >= self.exits[exit_id].eth_block + CHALLENGE_PERIOD
    assert self.exits[exit_id].challenge_count == 0

    send(self.exits[exit_id].owner, as_wei_value(self.exits[exit_id].offset, 'wei'))
    self.total_deposits -= as_wei_value(self.exits[exit_id].offset, 'wei')

@public
def challenge_completeness(
        exit_id: uint256,
        token_id: uint256,
) -> uint256:
    assert exit_id < self.exit_nonce

    self.challenges[self.challenge_nonce].exit_id = exit_id
    self.challenges[self.challenge_nonce].ongoing = True
    self.challenges[self.challenge_nonce].token_id = token_id
    self.exits[exit_id].challenge_count += 1

    challenge_id: uint256 = self.challenge_nonce
    self.challenge_nonce += 1
    return challenge_id

@public
def respond_completeness(challenge_id: uint256):
    assert self.challenges[challenge_id].ongoing == True

    self.challenges[challenge_id].ongoing = False
    exit_id: uint256 = self.challenges[challenge_id].exit_id
    self.exits[exit_id].challenge_count -= 1
