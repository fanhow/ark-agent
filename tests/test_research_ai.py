import copy
import json
import unittest
from pathlib import Path

from research import research_prompt, validate_ai_result


class ResearchAIRegressionTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.crew = json.loads((root / 'crew.json').read_text())
        self.brief = json.loads((root / 'public/briefs/2026-10-08.json').read_text())
        for item in self.brief['lenses'].values():
            item['take'] = '今日 AI 推演查不到／待更新，未設定金鑰或尚未完成。'

    def result(self):
        return {'headline': '依資料日期分析', 'stance': {'score': None, 'label': '證據不足'},
                'lenses': {p['id']: {'stance': None, 'take': '依其公開框架推演：已提供收盤價，仍缺估值資料。',
                                    'watch': p['watch']} for p in self.crew}, 'radioPoints': []}

    def test_prompt_contains_evidence_not_fallback_or_private_portfolio(self):
        self.brief['portfolio'] = {'secret': 'PRIVATE_PORTFOLIO_MARKER'}
        prompt = research_prompt(self.brief, self.crew)
        self.assertIn(self.brief['market'][0]['source'], prompt)
        self.assertNotIn('未設定金鑰或尚未完成', prompt)
        self.assertNotIn('PRIVATE_PORTFOLIO_MARKER', prompt)

    def test_copied_placeholder_or_empty_analysis_cannot_be_success(self):
        result = self.result()
        result['lenses'] = copy.deepcopy(self.brief['lenses'])
        with self.assertRaisesRegex(ValueError, '待更新提示'):
            validate_ai_result(self.brief, result)
        result = self.result()
        result['lenses']['buffett']['take'] = ' '
        with self.assertRaises(ValueError):
            validate_ai_result(self.brief, result)

    def test_unknown_stance_with_new_analysis_stays_unknown(self):
        candidate, _ = validate_ai_result(self.brief, self.result())
        self.assertIsNone(candidate['lenses']['buffett']['stance'])
        self.assertIn('缺估值資料', candidate['lenses']['buffett']['take'])


if __name__ == '__main__':
    unittest.main()
