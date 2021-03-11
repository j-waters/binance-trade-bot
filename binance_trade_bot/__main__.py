from datetime import datetime

import click
from click_default_group import DefaultGroup
from dateutil.parser import parse

from binance_trade_bot.backtest import backtest as _backtest, download_market_data
from .crypto_trading import main


@click.group(cls=DefaultGroup, default='trade', default_if_no_args=True)
def cli():
    pass


@cli.command()
def trade():
    main()


@cli.command()
@click.option('--start-date', default='2021-01-01', help='Start date', show_default=True)
@click.option('--end-date', default=datetime.today().strftime("%Y-%m-%d"), help='Start date', show_default=True)
@click.option('--interval', default=1, help='Number of minutes to move forward each iteration', show_default=True)
@click.option('--start-value', default=100, help='Starting balance of bridge coin', show_default=True)
@click.option('--start-coin', help='Start coin symbol, will pick first coin if not supplied', default=None)
@click.option('--fetch-data', help="Don't backtest, just download historic data", is_flag=True)
def backtest(start_date, end_date, interval, start_value, start_coin, fetch_data):
    if fetch_data:
        download_market_data(parse(start_date), parse(end_date), interval)
    else:
        _backtest(parse(start_date), parse(end_date), interval, start_value, start_coin)


if __name__ == '__main__':
    cli()
