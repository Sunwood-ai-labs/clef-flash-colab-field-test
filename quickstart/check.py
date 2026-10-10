"""Clef-flashの応答（JSON）を、先に決めておいた期待値と照らし合わせる。GPUは要らない。

使い方: python quickstart/check.py <応答のJSON> <期待値のJSON>
例:     python quickstart/check.py results/raw-responses/text-invoice-01.json quickstart/expected/text-invoice-01.json

期待値の書き方（質問のIDごとに1つ）:
  {"choice": "overdue"}   choice の答えがこの候補であること
  {"noul_above": 0.5}     noul（真である確率）がこの値を超えること
  {"noul_below": 0.5}     noul がこの値を下回ること
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
response = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
expected = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
answers = response.get('response', response)['answers']

passed = 0
for qid, rule in expected.items():
    answer = answers.get(qid, {})
    if 'choice' in rule:
        ok = answer.get('choice') == rule['choice']
        probs = '  '.join(f'{k}={v}' for k, v in sorted(answer.get('probabilities', {}).items(), key=lambda kv: -kv[1]))
        got, want = f'{answer.get("choice")}（{probs}）', rule['choice']
    else:
        value = answer.get('noul')
        above = 'noul_above' in rule
        limit = rule['noul_above'] if above else rule['noul_below']
        ok = isinstance(value, (int, float)) and (value > limit if above else value < limit)
        got, want = f'noul={value}', f'{limit}{"超" if above else "未満"}'
    passed += ok
    print(f'{"合格" if ok else "不合格"}  {qid}: {got}  期待: {want}')

usage = response.get('response', response).get('usage', {})
print(f'{passed}/{len(expected)} 問が期待どおり。入力トークン {usage.get("input_tokens")}')
sys.exit(0 if passed == len(expected) else 1)
