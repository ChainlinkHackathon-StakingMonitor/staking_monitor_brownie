from brownie import exceptions, StakingMonitor, network
import pytest

from scripts.helpful_scripts import (
    get_account,
    get_contract,
    LOCAL_BLOCKCHAIN_ENVIRONMENTS,
)
from web3 import Web3


@pytest.fixture
def deploy_staking_monitor_contract():
    # Arrange / Act
    interval = 3 * 60  # 3 minutes in seconds
    staking_monitor = StakingMonitor.deploy(
        get_contract("eth_usd_price_feed").address,
        get_contract("dai_token").address,
        get_contract("uniswap_v2").address,
        interval,
        {"from": get_account()},
    )
    block_confirmations = 6
    if network.show_active() in LOCAL_BLOCKCHAIN_ENVIRONMENTS:
        block_confirmations = 1
    staking_monitor.tx.wait(block_confirmations)
    # Assert
    assert staking_monitor is not None
    return staking_monitor


def test_can_get_latest_price(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    # Act
    value = staking_monitor.getPrice({"from": get_account()})
    # Assert
    assert isinstance(value, int)
    assert value > 0


def test_deposit(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    value = Web3.toWei(0.01, "ether")
    # Act
    deposit_tx_0 = staking_monitor.deposit({"from": get_account(), "value": value})
    deposit_tx_0.wait(1)

    value_1 = Web3.toWei(0.03, "ether")
    deposit_tx_1 = staking_monitor.deposit({"from": get_account(1), "value": value_1})
    deposit_tx_1.wait(1)

    # check that the balance has increased by the amount of the deposit
    assert staking_monitor.s_users(get_account().address)["depositBalance"] == value
    # check if address is added to watchlist
    assert staking_monitor.s_watchList(0) == get_account().address

    # check that the balance has increased by the amount of the deposit
    assert staking_monitor.s_users(get_account(1).address)["depositBalance"] == value_1
    # check if address is added to watchlist
    assert staking_monitor.s_watchList(1) == get_account(1).address


def test_get_deposit_balance(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    value = Web3.toWei(0.01, "ether")
    # Act
    deposit_tx = staking_monitor.deposit({"from": get_account(), "value": value})
    deposit_tx.wait(1)

    # returns tuple
    balance = staking_monitor.getDepositBalance({"from": get_account()})
    assert balance == value


def test_can_set_order(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    value = Web3.toWei(0.01, "ether")
    deposit_tx = staking_monitor.deposit({"from": get_account(), "value": value})
    deposit_tx.wait(1)
    price_limit = 3000000000000000000
    # percentage to swap is given in percentages, the portion will be calculated in the contract
    percentage_to_swap = 40
    # Act
    set_order_tx = staking_monitor.setOrder(
        price_limit, percentage_to_swap, {"from": get_account()}
    )
    set_order_tx.wait(1)
    # Assert
    assert (
        staking_monitor.s_users(get_account().address)["priceLimit"]
        == price_limit * 100000000
    )
    assert (
        staking_monitor.s_users(get_account().address)["percentageToSwap"]
        == percentage_to_swap
    )


def test_set_order_if_user_has_not_deposited_reverts(
    deploy_staking_monitor_contract,
):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    price_limit = 3000000000000000000
    # Act & Assert
    with pytest.raises(exceptions.VirtualMachineError):
        set_order_tx = staking_monitor.setOrder(
            price_limit, 40, {"from": get_account()}
        )
        set_order_tx.wait(1)


def test_set_balances_to_swap(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    user_account = get_account(2)
    assert user_account.balance() == 100000000000000000000
    # we deposit into the contract
    value = Web3.toWei(0.01, "ether")
    deposit_tx = staking_monitor.deposit({"from": user_account, "value": value})
    deposit_tx.wait(1)
    assert user_account.balance() == 99990000000000000000
    assert (
        staking_monitor.s_users(user_account.address)["latestBalance"]
        == 99990000000000000000
    )

    # Act
    # we set the order for this user
    price_limit = 3000000000000000000
    # percentage to swap is given in percentages, the portion will be calculated in the contract
    percentage_to_swap = 40

    set_order_tx = staking_monitor.setOrder(
        price_limit, percentage_to_swap, {"from": user_account}
    )
    set_order_tx.wait(1)

    # we mimic a staking reward by sending some ether from another account
    rewards_distributor = get_account(1)
    rewards_distributor.transfer(user_account, "1 ether")
    # assert account.balance() == 109990000000000000000

    tx = staking_monitor.setBalancesToSwap()
    tx.wait(1)
    watch_list_entry_for_address = staking_monitor.s_watchList(0)

    # Assert
    assert watch_list_entry_for_address == user_account.address
    assert (
        staking_monitor.s_users(user_account.address)["balanceToSwap"]
        == 400000000000000000
    )


def test_set_balances_to_swap_accrues(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    user_account = get_account(3)
    assert user_account.balance() == 100000000000000000000
    # we deposit into the contract
    value = Web3.toWei(0.01, "ether")
    deposit_tx = staking_monitor.deposit({"from": user_account, "value": value})
    deposit_tx.wait(1)
    assert user_account.balance() == 99990000000000000000
    assert (
        staking_monitor.s_users(user_account.address)["latestBalance"]
        == 99990000000000000000
    )

    # Act
    # we set the order for this user
    price_limit = 3000000000000000000
    # percentage to swap is given in percentages, the portion will be calculated in the contract
    percentage_to_swap = 40

    set_order_tx = staking_monitor.setOrder(
        price_limit, percentage_to_swap, {"from": user_account}
    )
    set_order_tx.wait(1)

    # we mimic a staking reward by sending some ether from another account
    rewards_distributor = get_account(1)
    rewards_distributor.transfer(user_account, "1 ether")
    # assert account.balance() == 109990000000000000000

    tx = staking_monitor.setBalancesToSwap()
    tx.wait(1)
    watch_list_entry_for_address = staking_monitor.s_watchList(0)

    assert watch_list_entry_for_address == user_account.address
    first_balance_to_swap = staking_monitor.s_users(user_account.address)[
        "balanceToSwap"
    ]
    # we send more ether to user_account to mimic another staking reward
    rewards_distributor.transfer(user_account, "1 ether")
    tx = staking_monitor.setBalancesToSwap()
    tx.wait(1)

    assert (
        staking_monitor.s_users(user_account.address)["balanceToSwap"]
        == 400000000000000000 + 400000000000000000
    )


def test_check_conditions_and_perform_swap(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    user_account = get_account(5)
    user_account_2 = get_account(6)
    assert user_account.balance() == 100000000000000000000
    # we deposit into the contract
    value = Web3.toWei(0.01, "ether")
    deposit_tx = staking_monitor.deposit({"from": user_account, "value": value})
    deposit_tx.wait(1)
    deposit_tx_2 = staking_monitor.deposit({"from": user_account_2, "value": value})
    deposit_tx_2.wait(1)
    assert user_account.balance() == 99990000000000000000
    assert (
        staking_monitor.s_users(user_account.address)["latestBalance"]
        == 99990000000000000000
    )

    # we get the latest price
    current_price = staking_monitor.getPrice({"from": get_account()})

    # we make sure that the price limit that will be set in the order is lower than the current price
    price_limit = current_price - 200000
    # percentage to swap is given in percentages, the portion will be calculated in the contract
    percentage_to_swap = 40

    set_order_tx = staking_monitor.setOrder(
        price_limit, percentage_to_swap, {"from": user_account}
    )
    set_order_tx.wait(1)
    set_order_tx_2 = staking_monitor.setOrder(
        price_limit, percentage_to_swap, {"from": user_account_2}
    )

    # we mimic a staking reward by sending some ether from another account
    rewards_distributor = get_account(1)
    rewards_distributor.transfer(user_account, "1 ether")
    rewards_distributor.transfer(user_account_2, "1 ether")
    # assert account.balance() == 109990000000000000000

    tx = staking_monitor.setBalancesToSwap()
    tx.wait(1)
    watch_list_entry_for_address = staking_monitor.s_watchList(0)

    assert watch_list_entry_for_address == user_account.address
    assert (
        staking_monitor.s_users(user_account.address)["balanceToSwap"]
        == 400000000000000000
    )

    # Act
    tx = staking_monitor.checkConditionsAndPerformSwap({"from": get_account()})
    tx.wait(1)

    # Assert
    assert staking_monitor.s_users(user_account.address)["priceLimit"] < current_price
    assert (
        staking_monitor.s_users(user_account.address)["DAIBalance"] == 500000000000000
    )
    assert staking_monitor.s_users(user_account.address)["balanceToSwap"] == 0


def test_can_call_check_upkeep(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    upkeepNeeded, performData = staking_monitor.checkUpkeep.call(
        "",
        {"from": get_account()},
    )
    assert isinstance(upkeepNeeded, bool)
    assert isinstance(performData, bytes)


def test_upkeep_needed(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    # get current price
    current_eth_price = staking_monitor.getPrice({"from": get_account()})
    # deposit some eth so that we can set a price limit
    deposit_value = Web3.toWei(0.01, "ether")
    deposit_tx = staking_monitor.deposit(
        {"from": get_account(), "value": deposit_value}
    )
    deposit_tx.wait(1)
    # set a price limit that is 100 less than current price so that upkeep is needed
    user_price_limit = current_eth_price - 100
    price_limit_tx = staking_monitor.setOrder(
        user_price_limit, 40, {"from": get_account()}
    )
    price_limit_tx.wait(1)

    # Act
    upkeepNeeded, performData = staking_monitor.checkUpkeep.call(
        "",
        {"from": get_account()},
    )
    assert upkeepNeeded == True
    assert isinstance(performData, bytes)


def test_upkeep_not_needed(deploy_staking_monitor_contract):
    # Arrange
    staking_monitor = deploy_staking_monitor_contract
    # get current price
    current_eth_price = staking_monitor.getPrice({"from": get_account()})
    # deposit some eth so that we can set a price limit
    deposit_value = Web3.toWei(0.01, "ether")
    deposit_tx = staking_monitor.deposit(
        {"from": get_account(), "value": deposit_value}
    )
    deposit_tx.wait(1)
    # set a price limit that is 100 less than current price so that upkeep is needed
    user_price_limit = current_eth_price + 100
    price_limit_tx = staking_monitor.setOrder(
        user_price_limit, 40, {"from": get_account()}
    )
    price_limit_tx.wait(1)

    # Act
    upkeepNeeded, performData = staking_monitor.checkUpkeep.call(
        "",
        {"from": get_account()},
    )
    assert upkeepNeeded == False
    assert isinstance(performData, bytes)
