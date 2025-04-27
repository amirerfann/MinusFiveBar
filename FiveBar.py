import requests
import pandas as pd
import backtrader as bt
from datetime import datetime
import matplotlib.pyplot as plt

# --- Fetch data ---
def get_datetime_timestamp(date_str):
    return int(pd.to_datetime(date_str).timestamp())

def ohlcv(symbol, resolution, start, stop):
    base_url = 'https://api.nobitex.ir/market/udf/history'
    ohlc_url = f"{base_url}?symbol={symbol}&resolution={resolution}&from={start}&to={stop}"

    try:
        response = requests.get(ohlc_url)
        response.raise_for_status()
        data = response.json()

        if not data.get('t') or data['s'] != 'ok':
            raise ValueError("Invalid or empty data returned from API")

        ohlcv_data = pd.DataFrame({
            'DateTime': pd.to_datetime(data['t'], unit='s'),
            'Open': pd.Series(data['o'], dtype=float),
            'High': pd.Series(data['h'], dtype=float),
            'Low': pd.Series(data['l'], dtype=float),
            'Close': pd.Series(data['c'], dtype=float),
            'Volume': pd.Series(data['v'], dtype=float)
        })
        return ohlcv_data

    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()
    except ValueError as e:
        print(f"Data error: {e}")
        return pd.DataFrame()

# --- Analyzer ---
class EquityCurveAnalyzer(bt.Analyzer):
    """Records portfolio value at the start of each new day."""
    def __init__(self):
        self.equity = []
        self.dates = []
        self.last_date = None

    def next(self):
        dt = self.strategy.datas[0].datetime.datetime(0)
        if self.last_date is None or dt.date() != self.last_date.date():
            self.equity.append(self.strategy.broker.getvalue())
            self.dates.append(dt)
            self.last_date = dt

    def get_analysis(self):
        return {'dates': self.dates, 'equity': self.equity}

# --- Strategy ---
class FiveBarStrategy(bt.Strategy):
    params = (('lookback', 3),)

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f'{dt.isoformat()} - {txt}')

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price}')

    def next(self):
        if len(self.datas[0]) <= self.params.lookback:
            return  # Not enough data

        diff = self.dataclose[0] - self.dataclose[-self.params.lookback]

        if not self.position:
            if diff > 0:
                self.log(f'BUY CREATE, Price: {self.dataclose[0]}')
                self.order = self.buy()
            elif diff < 0:
                self.log(f'SELL CREATE, Price: {self.dataclose[0]}')
                self.order = self.sell()
        else:
            if (self.position.size > 0 and diff < 0) or (self.position.size < 0 and diff > 0):
                self.log(f'CLOSE POSITION, Price: {self.dataclose[0]}')
                self.close()

# --- Run Backtest ---
def run_backtest():
    cerebro = bt.Cerebro()
    cerebro.addstrategy(FiveBarStrategy)

    df = ohlcv('btcusdt', 240, get_datetime_timestamp('2022-04-28'), get_datetime_timestamp('2025-04-28'))

    data = bt.feeds.PandasData(
        dataname=df,
        datetime='DateTime',
        open='Open',
        high='High',
        low='Low',
        close='Close',
        volume='Volume',
        openinterest=None
    )
    cerebro.adddata(data)
    cerebro.addanalyzer(EquityCurveAnalyzer, _name='equity_curve')
    cerebro.broker.set_cash(101)

    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    results = cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

    cerebro.plot()
    return results


results = run_backtest()
