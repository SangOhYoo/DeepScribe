import sys
from novel_translator.services.onomatopoeia import extract_regex

sample_text = """
にどうと
にどっと
になったと
になると
にスカート
にゾクッと
にハッと
にピクッと
にピクンと
にベトベト
ぬるっと
ねっちり
ねっとり
ねっとりと
ウエスト
のカント
のシャフト
はうっと
はぎゅっと
はしっと
はそっと
はぬるっと
はゴクリと
はドキッと
はハッと
はブーンと
ばんと
ぱっくり
びっくり
ぴったり
ふらふら
ぶるぶる
へなへな
べっとり
ほっと
ほんと
ぼんやり
まざまざ
ますます
まだまだ
まったくと
パクッと
ピクピク
ピチャピチャ
ブルブル
ブーンと
ベトベト
ムッチリ
メチャメチャ
メラメラ
"""

candidates = extract_regex(sample_text)
print("Extracted candidates:")
for cand in sorted(candidates):
    print(f" - {cand}")
