export interface Coin {
  symbol: string;
  enabled: boolean;
}

export interface ScoutLogEntry {
  from_coin: Coin;
  to_coin: Coin;
  current_ratio: number;
  target_ratio: number;
  current_coin_price: number;
  other_coin_price: number;
  datetime: string;
}

export type ScoutLogsGrouped = { [key: string]: ScoutLogEntry[] };

export interface Update<T> {
  table: string;
  data: T;
}
