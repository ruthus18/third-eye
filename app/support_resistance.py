import datetime as dt
import decimal
import math
import typing as tp
from decimal import Decimal

import numpy as np
import pandas as pd


class SupportResistanceSearch:

    def __init__(
        self,
        candles: pd.DataFrame,
        price_error: tp.Optional[Decimal] = None,
        min_size_of_batch: int = 5,
        recent_level_rate: int = 16,
    ):
        """Поиск ценовых уровней на основе исторических данных свечей

        Параметры:
            * candles: DataFrame со свечами
            * price_error:  Допустимый люфт цены (используется для объединения схожих ценовых уровней)
            * min_size_of_batch: Минимальный размер batch-а для разделения DataFrame-а со свечами
            * recent_level_rate: Множитель для установки приоритета новых уровней перед старыми

        Параметры по умолчанию подобраны для наиболее точного поиска уровней на дневке (CandleInterval=D1)
        """
        self.candles = candles
        self.price_error = price_error or self.default_price_error
        self.min_size_of_batch = min_size_of_batch
        self.recent_level_rate = recent_level_rate

        self._from_time = min(self.candles.time)
        self._to_time = max(self.candles.time)
        self._levels = None

    @property
    def default_price_error(self) -> float:
        # Define price error as 1/2 of volatility
        return np.mean(self.candles.high - self.candles.low) * 0.5  # type: ignore

    def _divide_to_batches(self, batches_num: int = 1) -> tp.List[pd.DataFrame]:
        """Разделить DataFrame на несколько равных по величине частей.

        Последний batch может быть не равен по величине предыдущим. Также, если невозможно разделить DataFrame
        на batches_num частей - количество батчей может быть меньше желаемого.
        """
        num_of_candles = len(self.candles)

        batch_size = math.ceil(num_of_candles / batches_num)
        start = 0
        stop = batch_size

        batches = []
        while start < num_of_candles:
            # TODO: Write as generator
            batches.append(self.candles[start:stop])

            start += batch_size
            stop += batch_size

        return batches

    def _find_similar_level(self, raw_levels: tp.List[tp.Dict[str, tp.Any]], price: Decimal) -> tp.Optional[int]:
        for i in range(len(raw_levels)):
            if abs(price - raw_levels[i]['price']) < self.price_error:
                return i

        return None

    def _time_weight(self, time: dt.datetime) -> float:
        max_delta = (self._to_time - self._from_time).days
        delta = (time - self._from_time).days
        return (delta * self.recent_level_rate / max_delta)  # type: ignore

    def _update_price_levels(
        self,
        raw_levels: tp.List[tp.Dict[str, tp.Any]],
        price: decimal.Decimal,
        time: dt.datetime,
        batch_size: int
    ) -> None:
        similar_level_id = self._find_similar_level(raw_levels, price)
        weight = batch_size + self._time_weight(time)

        if similar_level_id is None:
            raw_levels.append({'price': price, 'time': time, 'weight': weight})
        else:
            raw_levels[similar_level_id]['weight'] += weight
            raw_levels[similar_level_id]['time'] = min(
                time, raw_levels[similar_level_id]['time']
            )

    def _find_levels(self) -> tp.List[tp.Dict[str, tp.Any]]:
        """Найти ценовые уровни

        Алгоритм поиска работает следующим образом:

        1. Текуший набор свечей - все доступные свечи, переданные в объект класса
        2. Найти минимальную и максимальную цену для текущего набора свечей и
           задать их как ценовые уровни
        3. Назначить уровням вес исходя из размера текущего набора свечей и времени уровня
        4. Если уже есть такой ценовой уровень (с учетом люфта) - добавить вес к существующему весу уровня,
           сравнить даты уровней и выбрать минимальную
        5. Разделить набор свечей на (N+1) частей и повторить шаги 2-4 для каждой части
        """
        batch_iterations = len(self.candles) // self.min_size_of_batch
        raw_levels: tp.List[tp.Dict[str, tp.Any]] = []

        for num_of_batches in range(1, batch_iterations + 1):
            for batch in self._divide_to_batches(num_of_batches):
                batch_size = len(batch)

                max_price_id = batch.high.astype(float).argmax()
                max_price_row = batch.iloc[max_price_id]
                self._update_price_levels(raw_levels, max_price_row.high, max_price_row.time, batch_size)

                min_price_id = batch.low.astype(float).argmin()
                min_price_row = batch.iloc[min_price_id]
                self._update_price_levels(raw_levels, min_price_row.low, min_price_row.time, batch_size)

        max_weight = max([level['weight'] for level in raw_levels])
        return [
            {
                'price': level['price'],
                'time': level['time'],
                'significance': level['weight'] / max_weight,
            }
            for level in raw_levels
        ]

    def find_levels(self, significance_threshold: Decimal = Decimal(0.3)) -> pd.DataFrame:
        if self._levels is None:
            self._levels = pd.DataFrame.from_dict(self._find_levels())

        return self._levels[(self._levels.significance > significance_threshold)]  # type: ignore
