import app.chains.bsc as bsc


class FakeEth:
    chain_id = 56
    block_number = 123456


class FakeWeb3:
    def __init__(self, connected=True):
        self.connected = connected
        self.eth = FakeEth()

    def is_connected(self):
        return self.connected


def test_connect_delegates_to_web3_without_network(monkeypatch):
    fake = FakeWeb3(connected=True)
    monkeypatch.setattr(bsc, "w3", fake)

    assert bsc.connect() is True


def test_chain_id_reads_web3_eth_chain_id(monkeypatch):
    fake = FakeWeb3()
    monkeypatch.setattr(bsc, "w3", fake)

    assert bsc.chain_id() == 56


def test_latest_block_reads_web3_eth_block_number(monkeypatch):
    fake = FakeWeb3()
    monkeypatch.setattr(bsc, "w3", fake)

    assert bsc.latest_block() == 123456
