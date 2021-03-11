# binance-trade-bot

![github](https://img.shields.io/github/workflow/status/edeng23/binance-trade-bot/binance-trade-bot)
![docker](https://img.shields.io/docker/pulls/edeng23/binance-trade-bot)

> Automated cryptocurrency trading bot

## Why?

This script was inspired by the observation that all cryptocurrencies pretty much behave in the same way. When one spikes, they all spike, and when one takes a dive, they all do. _Pretty much_. Moreover, all coins follow Bitcoin's lead; the difference is their phase offset.

So, if coins are basically oscillating with respect to each other, it seems smart to trade the rising coin for the falling coin, and then trade back when the ratio is reversed.

## How?

The trading is done in the Binance market platform, which of course does not have markets for every altcoin pair. The workaround for this is to use Tether (USDT), which is stable by design, as a bridge currency.

<p align="center">
  Coin A → USDT → Coin B
</p>

The way the bot takes advantage of this behaviour is to always downgrade from the "strong" coin to the "weak" coin, under the assumption that at some point the tables will turn. It will then return to the original coin, ultimately holding more of it than it did originally. This is done while taking into consideration the trading fees.

<div align="center">
  <p><b>Coin A</b> → USDT → Coin B</p>
  <p>Coin B → USDT → Coin C</p>
  <p>...</p>
  <p>Coin C → USDT → <b>Coin A</b></p>
</div>

The bot jumps between a configured set of coins on the condition that it does not return to a coin unless it is profitable in respect to the amount held last. This means that we will never end up having less of a certain coin. The risk is that one of the coins may freefall relative to the others all of a sudden, attracting our reverse greedy algorithm.

## Binance Setup

-   Create a [Binance account](https://accounts.binance.com/en/register).
-   Enable Two-factor Authentication.
-   Create a new API key.
-   Get a cryptocurrency. If its symbol is not in the default list, add it.

## Tool Setup

### Install Python dependencies

Run the following line in the terminal: `pip install -r requirements.txt`.

### Create user configuration

Create a .cfg file named `user.cfg` based off `.user.cfg.example`, then add your API keys and current coin.

**The configuration file consists of the following fields:**

-   **api_key** - Binance API key generated in the Binance account setup stage.
-   **api_secret_key** - Binance secret key generated in the Binance account setup stage.
-   **current_coin** - This is your starting coin of choice. This should be one of the coins from your supported coin list. If you want to start from your bridge currency, leave this field empty - the bot will select a random coin from your supported coin list and buy it.
-   **bridge** - Your bridge currency of choice. Notice that different bridges will allow different sets of supported coins. For example, there may be a Binance particular-coin/USDT pair but no particular-coin/BUSD pair.
-   **tld** - 'com' or 'us', depending on your region. Default is 'com'.
-   **hourToKeepScoutHistory** - Controls how many hours of scouting values are kept in the database. After the amount of time specified has passed, the information will be deleted.
-   **scout_transaction_fee** - The transaction fee percentage. This value should be changed, for example, if you are [using BNB to pay for fees](https://www.binance.com/en/support/faq/115000583311-Using-BNB-to-Pay-for-Fees).
-   **scout_multiplier** - Controls the value by which the difference between the current state of coin ratios and previous state of ratios is multiplied. For bigger values, the bot will wait for bigger margins to arrive before making a trade.

#### Environment Variables

All of the options provided in `user.cfg` can also be configured using environment variables.

```
CURRENT_COIN_SYMBOL:
SUPPORTED_COIN_LIST: "XLM TRX ICX EOS IOTA ONT QTUM ETC ADA XMR DASH NEO ATOM DOGE VET BAT OMG BTT"
BRIDGE_SYMBOL: USDT
API_KEY: vmPUZE6mv9SD5VNHk4HlWFsOr6aKE2zvsw0MuIgwCIPy6utIco14y7Ju91duEh8A
API_SECRET_KEY: NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j
SCOUT_TRANSACTION_FEE: 0.001
SCOUT_MULTIPLIER: 5
SCOUT_SLEEP_TIME: 5
TLD: com
```

### Notifications with Apprise

Apprise allows the bot to send notifications to all of the most popular notification services available such as: Telegram, Discord, Slack, Amazon SNS, Gotify, etc.

To set this up you need to create a apprise.yml file in the config directory.

There is an example version of this file to get you started.

If you are interested in running a Telegram bot, more information can be found at [Telegram's official documentation](https://core.telegram.org/bots).

### Run

```shell
python -m binance_trade_bot
```

### Docker

The official image is available [here](https://hub.docker.com/r/edeng23/binance-trade-bot) and will update on every new change.

```shell
docker-compose up
```

if you only want to start the sqlitebrowser

```shell
docker-compose up -d sqlitebrowser
```

## Backtesting

You can test the bot on historic data to see how it performs

```shell
python -m binance_trade_bot backtest
```

```shell
Usage: binance_trade_bot backtest [OPTIONS]

Options:
  --start-date TEXT      Start date  [default: 2021-01-01]
  --end-date TEXT        Start date  [default: <today>]
  --interval INTEGER     Number of minutes to move forward each iteration
                         [default: 1]

  --start-value INTEGER  Starting balance of bridge coin  [default: 100]
  --start-coin TEXT      Start coin symbol, will pick first coin if not
                         supplied

  --fetch-data           Don't backtest, just download historic data
  --help                 Show this message and exit.

```

## Support the Project

<a href="https://www.buymeacoffee.com/edeng" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

## Join the Chat

-   **Discord**: [Invite Link](https://discord.gg/m4TNaxreCN)

## FAQ

A list of answers to what seem to be the most frequently asked questions can be found in our discord server, in the corresponding channel.

<p align="center">
  <img src = "https://usercontent2.hubstatic.com/6061829.jpg">
</p>

## Disclaimer

The code within this repository comes with no guarantee. Run it at your own risk.
Do not risk money which you are afraid to lose. There might be bugs in the code - this software does not come with any warranty.
