import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from macro_research import SPECS, observation, collect_one, collect

DAY = '2026-10-08'
CLOCK = datetime(2026, 10, 8, 7, 52, tzinfo=ZoneInfo('Asia/Taipei'))


class MacroDataTests(unittest.TestCase):
    def spec(self, id):
        return next(x for x in SPECS if x['id'] == id)

    def test_yen_uses_adjacent_valid_observations_and_not_range_start(self):
        # A missing day is not zero; a future observation cannot enter the snapshot.
        data = 'observation_date,DEXJPUS\n2026-09-01,120\n2026-10-02,150\n2026-10-05,.\n2026-10-06,147\n2026-10-08,160\n'
        r = collect_one(self.spec('yen'), DAY, lambda _: data, 'fetched', CLOCK)
        self.assertEqual((r['value'], r['change'], r['previousAsOf']), (147, -2, '2026-10-02'))
        self.assertEqual(r['ageDays'], 2)

    def test_rate_basis_points_and_vix_points_are_not_percent_returns(self):
        points = [('2026-10-02', 2.92), ('2026-10-05', 2.95)]
        rate = observation(self.spec('realYield'), points, DAY, '', '', '')
        vix = observation(self.spec('vix'), [('2026-10-02', 20), ('2026-10-05', 21)], DAY, '', '', '')
        self.assertEqual((rate['change'], rate['changeUnit']), (3, '基點'))
        self.assertEqual((vix['change'], vix['changeUnit']), (1, '點'))

    def test_weekly_negative_conditions_are_valid_and_compared_as_level_changes(self):
        r = observation(self.spec('conditions'), [('2026-09-25', -.510), ('2026-10-02', -.494)], DAY, '', '', '')
        self.assertEqual(r['value'], -.494)
        self.assertEqual(r['change'], .016)

    def test_gold_excludes_open_exchange_day_and_does_not_use_equity_close(self):
        # Taipei 07:52 is NY 19:52 the prior date; reject that NY day's futures bar.
        timestamps = [int(datetime(2026, 10, d, 9, tzinfo=ZoneInfo('America/New_York')).timestamp()) for d in [5, 6, 7]]
        data = {'chart': {'result': [{'meta': {'instrumentType': 'FUTURE', 'currency': 'USD', 'exchangeTimezoneName': 'America/New_York', 'shortName': 'Gold test'},
                 'timestamp': timestamps, 'indicators': {'quote': [{'close': [2000, 2020, 9999]}]}}]}}
        r = collect_one(self.spec('gold'), DAY, lambda _: json.dumps(data), '', CLOCK)
        self.assertEqual((r['value'], r['asOf'], r['change']), (2020, '2026-10-06', 1))

    def test_source_failure_is_isolated_and_missing_is_not_zero(self):
        def fetch(url):
            if 'DEXJPUS' in url:
                return 'DATE,DEXJPUS\n2026-10-02,150\n'
            raise TimeoutError('unavailable')
        radar = collect(DAY, fetch, '', CLOCK)
        self.assertEqual(len(radar['items']), 7)
        yen = next(x for x in radar['items'] if x['id'] == 'yen')
        self.assertEqual(yen['value'], 150)
        self.assertIsNone(yen['change'])
        self.assertTrue(all(x['value'] is None and x['history'] == [] for x in radar['items'] if x['id'] != 'yen'))

    def test_zero_real_yield_is_valid_but_nonfinite_values_are_not(self):
        r = observation(self.spec('realYield'), [('2026-10-02', -0.1), ('2026-10-05', 0), ('2026-10-06', float('nan'))], DAY, '', '', '')
        self.assertEqual((r['value'], r['change']), (0, 10))


if __name__ == '__main__':
    unittest.main()
