# Cloudflare Clef-flash を Google Colab の A100 で動かした：請求書と写真の判定で、期待した答えに0.97以上の確率が付いた

Cloudflareの判断モデル Clef-flash の公開重みを、Google ColabのA100（40GB）で動かしました。請求書のJSONと写真の2例に合計3つの質問を出し、3問とも、実験前に決めた期待どおりの答えに0.97以上の確率が返りました。判定1回は1.90秒と2.44秒、GPUメモリは最大18.0 GiBです。L4（22 GiB）ではモデルの読み込みでメモリが足りず、新しい Clef-omni は必要なGPUを確保できなかったため動かせていません。

![3つの質問に付いた確率](https://raw.githubusercontent.com/Sunwood-ai-labs/clef-flash-colab-field-test/main/assets/chart-answers.png)

## わかったこと

1. **Clef-flashの公開重みは、ColabのA100で公式の手順のまま動く。** 重みの取得から2例の判定まで、全体で74.3秒でした。
2. **文章ではなく、候補ごとの確率が返る。** 請求書の状態は3択のうち `overdue` に0.9729、「合計は1,000ドルを超えるか」に0.9738、写真の「手が複数のキャンディを持っているか」に0.9716でした。
3. **GPUは24GBでは足りなかった。** 動作中の使用量は約18 GiBですが、読み込みの途中で一時的にその倍近くを要求するため、L4（22 GiB）では止まりました。

これは2例・3問の動作確認です。請求書の入力には状態がそのまま書かれており、難しい問題ではありません。正解率や速度を評価した実験ではなく、Cloudflareが発表した料金・速度を再現したものでもありません。

## Clef-flashとは

Clef-flashは、文章を生成するAIではありません。「入力」と「質問」と「答えの候補」を渡すと、候補それぞれの確率を返す判断モデルです。問い合わせをどの部署へ回すか、請求がどの状態か、写真が条件を満たすか、といった「決められた選択肢から選ぶ」仕事に向けて作られています。

質問には3つの型があります。

| 型 | 何を返すか | 今回の実験での例 |
| --- | --- | --- |
| choice | 名前の付いた候補それぞれの確率 | 請求書の状態は paid / overdue / draft のどれか |
| noul | 真である確率（0〜1） | 合計は1,000ドルを超えるか |
| score | 順序のある段階それぞれの確率 | 今回は使っていない |

公式の資料に書かれている仕様は次のとおりです。

| 項目 | 内容 |
| --- | --- |
| 開発元 | Cloudflare |
| 構成 | Qwen3.5-9B（90億パラメータ）に、判断用のヘッドを足したもの |
| 入力 | テキスト、JSON、画像、動画 |
| 出力 | 質問ごとの確率。文章は生成しない |
| 1回の要求に入れられる質問 | 1〜64個 |
| ホスト版（Workers AI）の料金 | 入力100万トークンあたり0.038ドル。出力への課金はない |
| ホスト版の入力上限 | 24,576トークン |
| 公開重み | Hugging Faceで配布。Apache-2.0。約19.1 GB |
| 公式が動作を確認した環境 | H200が1枚、PyTorch 2.11、Transformers 5.10.2 |

トークンは、モデルが文章や画像を数えるときの単位です。今回の請求書の例は質問と候補を含めて260トークン、写真の例は927トークンでした。

Cloudflareは2026年10月9日の記事で、音声と動画も扱う Clef-omni の追加、Clef-flashの値下げ（入力100万トークンあたり0.09ドルから0.038ドルへ）、ホスト版Clefの高速化を発表しました。Clef-flashの値下げと同時に、ホスト版の入力上限は約64,000トークンから24,576トークンに縮んでいます。これらはCloudflareの発表値で、今回は確かめていません。

- 発表記事: https://blog.cloudflare.com/clef-faster-cheaper-multimodal/
- Workers AIの仕様: https://developers.cloudflare.com/workers-ai/models/clef-flash/
- 公開重みとモデルカード: https://huggingface.co/Cloudflare/clef-flash

## 何を試したのか

公開重みを自分で用意したGPUで動かし、「入力と質問を渡すと確率が返る」という基本の動作を、テキストと画像で1例ずつ確かめました。Cloudflareのホスト版APIは使っていません。

![Clef-flashに入力した2件](https://raw.githubusercontent.com/Sunwood-ai-labs/clef-flash-colab-field-test/main/assets/inputs-overview.jpg)

写真は、Hugging Faceが公開しているドキュメント用の画像です。4032×3024の元画像を1024×768に縮めて渡しました。質問と候補は英語のまま渡しています。

登場するモデルと道具の役割は次のとおりです。

| 名前 | 役割 | たとえると |
| --- | --- | --- |
| Clef-flash | 今回動かした主役。入力を読み、候補に確率を付ける | マークシートの各選択肢に「自信の度合い」を書き込む採点係 |
| Clef-omni | 音声と動画も扱える新しいモデル。今回は動かせなかった | 録音や映像も確認できる採点係 |
| Google Colab | GPUを時間単位で借りる場所 | 時間貸しの作業場 |
| Colab CLI | 手元のターミナルからColabを操作する道具 | 作業場に指示を送る内線電話 |

## 実験のやり方

入力、質問、期待する答え、合格の基準を、モデルを動かす前にJSONファイルへ書いて固定しました。結果を見てから基準を動かさないためです。

| 例 | 質問 | 合格の基準 |
| --- | --- | --- |
| 請求書 | 状態はどれか（3択） | `overdue` が選ばれる |
| 請求書 | 合計は1,000ドルを超えるか | 真である確率が0.5を超える |
| 写真 | 手が複数のキャンディを持っているか | 真である確率が0.5を超える |

モデルは、配布物に入っている公式のコード（`joint_schema_model.py`）の `load_release_model` で読み込み、`systemone` という関数で判定しました。Hugging Faceのページに自動で表示される `pipeline()` や `generate()` の例は、土台のQwenに文章を書かせるもので、Clefの判断ヘッドを通りません。その例が動いても、Clefを動かしたことにはなりません。

重みは特定の版（revision `8b2e5fd1`）に固定し、公式コードのSHA-256も実行のたびに照合しています。

## 結果

### 3問とも期待どおりの答えが返った

冒頭のグラフの元になった数値です。

| 例と質問 | 返ってきた答え | 確率 | 判定 |
| --- | --- | ---: | --- |
| 請求書：状態 | overdue | 0.9729 | 合格 |
| 請求書：1,000ドル超か | 真 | 0.9738 | 合格 |
| 写真：手がキャンディを持つか | 真 | 0.9716 | 合格 |

請求書の状態では、選ばれなかった候補の確率も返ります。`paid` が0.0177、`draft` が0.0095で、3つを足すとほぼ1になります。「どれを選んだか」だけでなく「ほかの候補とどれだけ差があったか」が数字で残るのは、後段のプログラムで「確率が低いときは人に回す」といった処理を書きやすい形です。

結果を確認するために作った閲覧画面でも、保存したJSONと同じ値が表示されることを確かめました。

![請求書の例の入力と回答](https://raw.githubusercontent.com/Sunwood-ai-labs/clef-flash-colab-field-test/main/assets/screenshot-text.jpg)

![写真の例の入力と回答](https://raw.githubusercontent.com/Sunwood-ai-labs/clef-flash-colab-field-test/main/assets/screenshot-image.jpg)

### GPUメモリは動作中18 GiB、読み込み中はその倍近く

![L4とA100のGPUメモリ](https://raw.githubusercontent.com/Sunwood-ai-labs/clef-flash-colab-field-test/main/assets/chart-memory.png)

| GPUと場面 | 全容量 | 使用量 |
| --- | ---: | ---: |
| L4：読み込みの途中 | 22.03 GiB | 17.76 GiB使用中に、追加で17.23 GiBを要求して停止 |
| A100：読み込み直後 | 39.49 GiB | 17.75 GiB |
| A100：請求書の判定中 | 39.49 GiB | 最大17.83 GiB |
| A100：写真の判定中 | 39.49 GiB | 最大18.00 GiB |

動作中の使用量だけを見ればL4にも収まりそうですが、実際には読み込みの途中で止まりました。原因は次の節で説明します。

### 74秒のほとんどは準備

![実行時間の内訳](https://raw.githubusercontent.com/Sunwood-ai-labs/clef-flash-colab-field-test/main/assets/chart-time.png)

| 段階 | 時間 |
| --- | ---: |
| 重みの取得（約19.1 GB） | 49.1秒 |
| モデルの読み込み | 20.1秒 |
| 請求書の判定（260トークン） | 1.90秒 |
| 写真の判定（927トークン） | 2.44秒 |
| 合計 | 74.3秒 |

判定時間は、それぞれ1回だけ測った値です。モデルを読み込んだ直後の最初の呼び出しを含むため、繰り返したときの速さはわかりません。高速化用のライブラリ（`flash-linear-attention`）は入れておらず、PyTorchの標準実装で動いています。Cloudflareはホスト版の応答時間を数百ミリ秒と発表していますが、配信の仕組みが違うので、今回の秒数とは比べられません。

## 原因の切り分け

L4で動かなかった理由を確かめました。

| 疑った要因 | 確かめ方 | 結果 | 判定 |
| --- | --- | --- | --- |
| 前の実行のモデルがGPUに残っていた | 実行の記録で読み込みの回数を確認 | 読み込みは1回だけ。その前の呼び出しは重みの取得中に時間切れになり、読み込みに進んでいない | 該当しない |
| 入力や質問が大きすぎた | エラーの発生箇所を確認 | 判定に入る前、`load_release_model` の中で停止 | 該当しない |
| 読み込み時の一時的なメモリ確保 | エラーの内容を確認 | Transformersの読み込み処理が、17.76 GiBを使用中にさらに17.23 GiBを確保しようとした | これが原因 |
| GPUを大きくすれば動くか | モデル・入力・手順を変えず、GPUだけA100に変更 | 2例とも成功 | 確認できた |

止まったのは、Transformersが重みを読み込む前にメモリをまとめて確保する処理（`caching_allocator_warmup`）です。合計で約35 GiBが要る計算になり、22 GiBのL4には収まりません。

量子化（重みを粗くして小さくする方法）や、この確保を避ける読み込み方は試していません。L4で動かす方法が「ない」とは言えず、「公式の手順のままでは動かなかった」が今回確かめた範囲です。

## 舞台裏

実験は2026年10月10日に行いました。時刻は日本時間です。

| 時刻 | 起きたこと | 対処 |
| --- | --- | --- |
| 16:07 | L4のColabセッションを作成 | Transformers 5.10.2を導入 |
| 16:14 | 導入直後の確認で接続が切れた | カーネルを再起動して復旧。L4とCUDA、ライブラリの版を確認 |
| 18:02〜18:06 | 設定ファイルのアップロードが3回失敗 | 送り先のパスを変えても解消せず |
| 18:10 | セッションそのものが失われていた（404と401の応答）と判明 | セッションを作り直し、入力ファイルはColabの中でスクリプトから作る方法に変更 |
| 18:12 | 重みの取得後、読み込みでGPUメモリ不足 | 失敗の記録を保存し、GPUを変える方針に |
| 18:55 | A100のセッションを作成 | 同じモデル・入力・手順のまま再実行 |
| 19:20〜19:21 | 2例とも成功 | 結果のJSONを保存 |
| 19:45 | A100の停止コマンドが404を返した | 利用状況の一覧でA100の割り当てが消えていることを確認 |
| 19:46 | Clef-omni用にH100を要求したが拒否された | 利用枠または契約条件の不足。追加の購入はせず、未実行として記録 |

アップロードの失敗は、当初はパスの指定の問題だと考えていましたが、実際にはセッションが失われていたことが原因でした。Colab CLIでコマンドが続けて失敗するときは、先にセッションの状態を確認するのが近道です。

Clef-omniは、公式のモデルカードに「BF16で約64GBのGPUメモリが必要、H200で確認」とあります。確保できたA100は40GBで足りず、より大きいH100は割り当てを受けられませんでした。重みを量子化して無理に動かすことはしていません。

## 評価と次に試すこと

![試せたことと試せなかったこと](https://raw.githubusercontent.com/Sunwood-ai-labs/clef-flash-colab-field-test/main/assets/chart-coverage.png)

| 観点 | 良い点 | 課題 |
| --- | --- | --- |
| 動かしやすさ | 公式コードの2つの関数を呼ぶだけで判定できる | Hugging Faceのページに自動表示される例は別物で、間違えやすい |
| 出力 | 候補ごとの確率が返り、後段の処理に使いやすい | 確率がどの程度あてになるかは、今回の3問ではわからない |
| 必要なGPU | A100の40GBなら余裕がある | 24GB級では公式の手順のまま読み込めない |
| 入力の幅 | テキストと画像を同じ形式で渡せる | 動画、複数画像、長い入力は未確認 |

この実験から言えないこと。

- Clef-flashの正解率。3問はどれも答えがはっきりしており、迷うような例を含んでいません。
- 繰り返し呼び出したときの速度や、同時に多数の要求をさばく性能。
- Cloudflareのホスト版（Workers AI）の料金、速度、上限。
- Clef-omniの音声・動画の性能。
- 日本語の入力や質問での動作。

次に試すなら、という候補です。

- [ ] 答えが紛らわしい例（状態が書かれていない請求書、キャンディ以外を持つ手の写真）で、確率がどう変わるかを見る
- [ ] 同じ入力を繰り返し判定し、2回目以降の時間を測る
- [ ] 日本語の入力と質問で試す
- [ ] Workers AIのホスト版に同じ2例を送り、答えと応答時間を比べる
- [ ] 64GB以上のGPUを確保して、Clef-omniに音声と動画を渡す

## 動かし方

コードと実測結果は、次のリポジトリにあります。

https://github.com/Sunwood-ai-labs/clef-flash-colab-field-test

### 用意するもの

| もの | 内容 |
| --- | --- |
| GPU | メモリが24GBを超えるもの。実験ではColabのA100（40GB） |
| Python環境 | PyTorch 2.11、Transformers 5.10.2、Pillow |
| ディスク | 重みの保存に約20 GB |
| Hugging Faceのログイン | 不要（重みは公開されている） |

Colabの有料GPUは、使った時間に応じて利用枠（コンピューティングユニット）を消費します。

### 手順1：GPUランタイムを用意する

実験ではColab CLIを使いました。ノートブックの画面からA100のランタイムを選んでも同じです。

```bash
colab new -s clef --gpu A100
colab install -s clef transformers==5.10.2
colab restart-kernel -s clef
```

Transformersを入れ替えたあとは、カーネルの再起動が要ります。

### 手順2：判定を実行する

```bash
colab exec -s clef --timeout 1800 -f quickstart/clef_flash_demo.py
```

ノートブックで動かす場合は、このファイルの中身をセルに貼って実行します。核になるのは次の部分です。

```python
model_path = snapshot_download(repo_id=MODEL_ID, revision=REVISION, local_dir=MODEL_DIR, token=False)

# 通常の pipeline() や generate() ではなく、配布物に入っている公式の判断ヘッドを通す
sys.path.insert(0, str(model_path))
from joint_schema_model import load_release_model, systemone

model, processor = load_release_model(model_path, device="cuda")
response = systemone(model, processor, request)
```

自分のデータで試すときは、ファイルの先頭にある `REQUESTS` を書き換えます。

```python
"text-invoice-01": {
    "state": {"invoice": {"vendor": "Acme", "total": 1250.0, "currency": "USD", "status": "overdue"}},
    "questions": {
        "status": {
            "type": "choice",
            "instructions": "What is the invoice status?",
            "criteria": {"paid": "Invoice is paid.", "overdue": "Invoice is past due.", "draft": "Not sent."},
        },
        "large": {"type": "noul", "instructions": "Is the total above 1000 USD?"},
    },
},
```

- ファイル全体: https://github.com/Sunwood-ai-labs/clef-flash-colab-field-test/blob/main/quickstart/clef_flash_demo.py

このファイルは、実験で動かしたスクリプトから取得・読み込み・判定の部分を取り出して短くしたものです。この形のままでは実行していません。実験で実際に動かしたものは `experiment/run_clef.py` です。

- 実験で動かしたスクリプト: https://github.com/Sunwood-ai-labs/clef-flash-colab-field-test/blob/main/experiment/run_clef.py

### 手順3：出力を読む

`systemone` は次の形のJSONを返します。

```json
{
  "answers": {
    "large": {"noul": 0.9738, "type": "noul"},
    "status": {
      "choice": "overdue",
      "confidence": 0.9729,
      "probabilities": {"draft": 0.0095, "overdue": 0.9729, "paid": 0.0177},
      "type": "choice"
    }
  },
  "model": "clef-flash",
  "usage": {"input_tokens": 260, "output_tokens": 0}
}
```

| 項目 | 意味 |
| --- | --- |
| choice | 選ばれた候補 |
| confidence | 選ばれた候補の確率 |
| probabilities | すべての候補の確率 |
| noul | 真である確率 |
| input_tokens | 入力・質問・候補を合わせたトークン数 |

### 手順4：期待値と照らし合わせる

応答を保存したJSONと、先に決めておいた期待値を比べます。GPUは要りません。リポジトリに入っている実験の応答で、そのまま試せます。

```bash
python quickstart/check.py results/raw-responses/text-invoice-01.json quickstart/expected/text-invoice-01.json
```

```text
合格  status: overdue（overdue=0.9729  paid=0.0177  draft=0.0095）  期待: overdue
合格  large: noul=0.9738  期待: 0.5超
2/2 問が期待どおり。入力トークン 260
```

この採点スクリプトは、実験の実際の応答2件にかけて、記事と同じ数字と判定になることを確認しています。

- 採点スクリプト: https://github.com/Sunwood-ai-labs/clef-flash-colab-field-test/blob/main/quickstart/check.py

### 手順5：ランタイムを止める

```bash
colab stop -s clef
colab usage
```

実験では停止コマンドがエラーを返したのに、割り当ては消えていました。止めたあとは、利用状況の一覧で残っていないことを確かめてください。

### リポジトリの中身

| フォルダ | 内容 |
| --- | --- |
| quickstart | 自分のデータで試すスクリプトと、採点スクリプト |
| experiment | 実験で実際に動かしたスクリプトと、事前に固定した入力・期待値 |
| results | A100での結果、L4での失敗の記録、モデルの生の応答 |
| assets | グラフ、入力のタイル画像、それらを作るスクリプト |
| docs | 実行の詳細な報告と、公式資料の調査メモ |

## 実行条件と指標の定義

| 項目 | 値 |
| --- | --- |
| 実行日時 | 2026年10月10日 19:20〜19:21（日本時間） |
| モデル | Cloudflare/clef-flash、revision 8b2e5fd17c09fd49bc2880b805d5323ec7ff4ff3 |
| GPU | NVIDIA A100-SXM4-40GB（Google Colab） |
| 数値の精度 | BF16（公式の読み込み関数の既定） |
| ソフトウェア | Python 3.13.15、PyTorch 2.11.0+cu130、Transformers 5.10.2、Pillow 11.3.0 |
| 操作に使った道具 | Colab CLI 0.7.2（WSLのUbuntu 24.04から） |
| 画像の前処理 | RGBに変換し、長辺を1024ピクセルに縮小（LANCZOS） |

| 指標 | 定義 | 限界 |
| --- | --- | --- |
| 合格 | 事前に固定した期待値を満たしたか | 3問だけ。正解率ではない |
| 判定時間 | `systemone` の呼び出し1回にかかった時間。GPUの処理完了を待って測定 | 各1回の測定。重みの取得と読み込みは含まない |
| GPUメモリ | PyTorchが確保した量の最大値 | PyTorch以外が使う分は含まない |
| 入力トークン | `systemone` が返した `input_tokens` | 質問と候補の文も含む |

公開にあたり、結果と設定のJSONに含まれていたローカルのパスは置き換えました。数値は変えていません。

## 参考リンク

- Cloudflareの発表記事: https://blog.cloudflare.com/clef-faster-cheaper-multimodal/
- Clef-flashのモデルカード: https://huggingface.co/Cloudflare/clef-flash
- 実験で固定した版: https://huggingface.co/Cloudflare/clef-flash/tree/8b2e5fd17c09fd49bc2880b805d5323ec7ff4ff3
- Workers AIのClef-flash: https://developers.cloudflare.com/workers-ai/models/clef-flash/
- Clef-omniのモデルカード: https://huggingface.co/Cloudflare/clef-omni
- 写真の出典: https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/p-blog/candy.JPG
- この実験のリポジトリ: https://github.com/Sunwood-ai-labs/clef-flash-colab-field-test
- 公式資料の調査メモ: https://github.com/Sunwood-ai-labs/clef-flash-colab-field-test/blob/main/docs/sources.md

#ClefFlash #Cloudflare #マルチモーダルAI #GoogleColab #AI
