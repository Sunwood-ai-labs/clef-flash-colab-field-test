# Cloudflare CLEF 一次資料メモ

調査日: 2026-10-10 (JST)  
対象: [Clef-omni発表記事](https://blog.cloudflare.com/clef-faster-cheaper-multimodal/) と Clef / Clef-flash / Clef-omni の現行仕様  
担当範囲: 一次資料調査のみ。モデル実行・Colab GPU実験は別担当。ここに性能の手元実測はない。

## 要点

Clefはチャット文章を自由生成するLLMではなく、入力状態と型付き質問を一度に読み、許可された各回答の確率を返す「判定モデル」。`noul` (真偽)、`choice` (名前付き選択肢)、`score` (順序付き段階) を使う。候補選択、分類、振り分け、構造化評価に向く一方、自由文の説明文を返すモデルとして扱うと設計がずれる。[Cloudflare記事](https://blog.cloudflare.com/clef-faster-cheaper-multimodal/)、[OmniのHugging Faceモデルカード](https://huggingface.co/Cloudflare/clef-omni)

- 画像・動画を含む判定で小さめの重みを試すなら **Clef-flash**。ただしWorkers AIホスト版は24,576トークン、入力100万トークンあたり$0.038。Flashの重み自体は記事上256k対応のままだが、公式`encode_record`の既定`max_length`は16,384で、実装・起動条件を確認せず256kを使えるとは言えない。
- 音声と動画を一つの判定要求にまとめるなら **Clef-omni**。ホスト版は64,000トークン、入力100万トークンあたり$0.15。自前実行はBF16で約64GBのGPUメモリを要し、公式確認環境は単一H200。
- 大きめのテキスト判定・画像判定でホスト版のコンテキスト長を重視するなら **Clef**。現行Workers AI docsは65,536トークン、$0.24/百万入力トークン。
- 「高速化したClef」は重み更新ではなくWorkers AIのサービング基盤の変更。記事はSGLang移行を挙げ、重みは新規公開していない。
- 記事の平均的なベンチマーク勝敗だけで選ばない。OmniはHome appliance、When2Call、BRIGHT、RAGTruthなどで他モデルに大きく劣る公表値がある。音声・動画専用の精度評価は公表表から確認できない。

## 3モデルの違い

| モデル | 基盤・構成 | モダリティ | Workers AIホスト版 | 公式カードの自前実行情報 |
|---|---|---|---|---|
| Clef | Qwen3.8-27B、27Bのdenseモデル + joint schema head | テキスト、JSON、画像、動画 | 65,536 tokens、$0.24/百万入力tokens | `torch` 2.11、`transformers` 5.10.2、単一H200で確認。BF16重みだけの概算下限は約54GB (27B×2 byte、推論実測ではない)。画像/動画は`pillow`。 |
| Clef-flash | Qwen3.5-9B、9Bのdenseモデル + joint schema head | テキスト、JSON、画像、動画 | 24,576 tokens、$0.038/百万入力tokens | `torch` 2.11、`transformers` 5.10.2、単一H200で確認。BF16重みだけの概算下限は約18GB (9B×2 byte、推論実測ではない)。画像/動画は`pillow`。 |
| Clef-omni | Qwen3-Omni-30B-A3B-Instruct由来、MoE・3B active + joint schema head | テキスト、JSON、画像、音声、動画 | 64,000 tokens、$0.15/百万入力tokens | `torch` 2.11、`transformers` 5.10.2、単一H200で確認。BF16のbackboneに約64GB GPUメモリ。画像は`pillow`、音声/動画は`av`。 |

Clef-omniのカードは基盤を「30B-A3B」、Hugging Face表示のモデル総数を「35B parameters」と記載する。音声出力用talker/code2wav重みは配布ファイルに含まれるが、公式`load_release_model`はそれらをロードしない。したがって「3B active」をロード時VRAMや保存容量と同じ値として扱わない。[Omniカード](https://huggingface.co/Cloudflare/clef-omni)

3つのHugging Faceリポジトリはいずれもカード上のライセンスがApache-2.0。重みを利用する場合は各リポジトリのLICENSEと基盤モデルの条件を確認する。Workers AI APIの利用条件・課金は重みのライセンスと別である。

## ホスト版と重みの条件は別

| 項目 | Hosted Workers AI | Hugging Face重み / 公式コード |
|---|---|---|
| Clef context | 65,536 tokens (発表記事は64kと概数表記) | `encode_record`の既定`max_length`は16,384。自前実行で上限を上げる場合は実際の構成・VRAM・精度を別確認する。 |
| Clef-flash context | 24,576 tokens。価格引き下げと一緒に64kから縮小 | 発表記事は配布重みを変更せず256k対応と説明。ただし公式カードの既定`max_length`は16,384、SGLang PRの精度テストは最大32k状態。これらは「重みが訓練された上限」と「今使う推論経路の既定/検証範囲」が違うことを示す。 |
| Clef-omni context | 64,000 tokens | `encode_record`の既定`max_length`は64,000。BF16で約64GB GPUメモリ、単一H200での確認。 |
| 価格 / 課金 | 上記モデル別の入力token単価。モデルdocsは出力token課金なし、画像/音声/動画も入力tokensとして計上と記す。 | 重みの利用料はモデルライセンスと別。GPU/Colab実行の費用・利用枠はその環境側。 |

Workers AIの共通価格ページはFreeに1日10,000 Neurons、超過分はWorkers Paidで$0.011/1,000 Neurons、日次リセットは00:00 UTCと説明する。モデルページに表示されたトークン単価と無料枠は別の表示単位なので、無料枠を固定のトークン数に換算しない。[Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)

## 判定APIと制限

Workers AI RESTの形は `POST /client/v4/accounts/{account_id}/ai/run/@cf/cloudflare/{model}`。JSONは`model`, `state`, `questions`と任意のメディア入力。Jev / SystemOne互換APIで、質問ごとの`answers`と`usage`を返す。Omniの自前Python側も`systemone()`が同じ型のrequest/responseを扱う。質問は1要求につき1〜64件。`choice`の`criteria`はID→説明のmap、`score`は順序付き説明配列。

**Omniホスト版の入力制限 (現行Cloudflare docs):**

- 画像: PNG/JPEG/WebP、最大4件。各4 MiB・16MPまで、合計decoded 8 MiBまで。画像のURL直指定は不可。1画像64〜1,024 input tokens。
- 音声: 最大4件、各8 MiB・300秒まで。音声と動画合わせたdecoded容量は16 MiBまで。URL直指定は不可。
- 動画: 最大2件、各16 MiB・60秒まで。2 fpsでサンプリング。音声トラックは要求中の全動画に音声がある場合に利用。音声と動画合わせたdecoded容量は16 MiBまで。URL直指定は不可。
- 画像は32px単位へ調整し、最大1,024 tokens。音声は約780 tokens/分。動画は480pで約8,600 frame tokens/分、最大解像度では約15,400 tokens/分+音声分。
- メディアと質問を合わせて64k contextを超えると失敗し、収まる場合は残りに合わせてテキスト`state`が切り詰められる。長尺ほど画像・動画の画質/フレーム情報と費用の両方が効く。

**Clef/Clef-flash hosted videoの資料差:** 現行モデルdocsの説明文は「画像または動画」と書く一方、同ページのAPI Parametersには`images`だけがあり、`videos`項目がない。Hugging Faceカードと発表記事は動画フレーム配列を説明している。したがってセルフホストの動画対応は資料上確認できるが、現行Workers AIのClef/Flashで`videos` fieldが公開APIとして有効かは一次資料間で曖昧。実際のAPI要求前に検証が必要で、現時点ではホスト版の動画対応を断定しない。

## 正式な自前推論経路と落とし穴

Clefは通常のchat generationではなく、配布されたbackboneと`joint_head.safetensors`を一緒に動かす。公式Hugging FaceカードのPython例は次の流れ。

1. `snapshot_download("Cloudflare/clef-omni")`でスナップショット取得。
2. 配布ディレクトリから`joint_schema_model`をimport。
3. `load_release_model(path, device="cuda")`でbackbone・joint head・processorを読み込む。
4. `encode_record(...)`、`collate_records(...)`を通し、`model(batch)`のlogitsを質問ごとにsoftmaxして確率へ変換する。互換形式なら同モジュールの`systemone()`を使う。

Hugging Faceページ上部に表示されるTransformersの自動生成`pipeline(...)`や`model.generate(...)`例は、画像を説明する一般的なQwenチャット生成例であり、Cloudflareのtyped decision headを通す例ではない。これを成功させてもClef判定機能を実行した証拠にならない。カード内の`joint_schema_model.py` + `load_release_model`経路を使う。

SGLangの同様の注意点: 標準Hugging Face生成例の`/v1/chat/completions`と、Clef判定を返す`/v1/systemone`は別ルート。一般のchat completionを動かしただけではheadの判定を検証できない。

## SGLangの現行対応範囲

- [PR #42721](https://github.com/sgl-project/sglang/pull/42721)は2026-10-09にmainへmerge済み。ClefとClef-flashを`/v1/systemone`から判定する変更で、Omniは対象・検証モデルに含まれない。
- PRテストは1×H200、BF16。元モデルの`load_release_model`結果と比較し、12 payloadでtop choiceが全件一致。状態は最大32k tokens、質問3/64、選択肢順入れ替え、画像1/4件など。これはPR中の検証値で、今回実行した測定ではない。
- PR記載の制約はTP=1/PP=1、radix cacheなし、chunked prefillなし、CUDA graphsなし。`/v1/decisions`、`/encode`、`chat_template_kwargs`、LoRA要求は拒否。
- 同PRのH200 c=1中央値はClef 67/572/755 ms、Flash 38/186/247 ms (それぞれ3問511 tokens / 64問6.5k tokens / 3問255選択肢8.8k tokens)。25要求warm-up後の中央値で、OmniやWorkers AI hosted latencyと比較できる同条件値ではない。
- Cloudflare記事はこのサポートをSGLang 0.5.22に収録予定と記載。2026-10-10にGitHub Releases APIで確認した最新tagはv0.5.21 (2026-10-02)。PRはmainに入ったが、該当安定版への収録は未確認。Clef/FlashはHugging Faceカードの`dev-clef`イメージ例を参照し、実行担当が使用tag/commitを固定する。
- Omni Hugging Faceページの上部に自動生成SGLang `/v1/chat/completions`例がある一方、カード本文のSGLang項目は “coming soon!”。Omniのdecision headを使うSGLang正式経路は今回の一次資料では未確認。上のPRをOmniへ一般化しない。

## 性能の読み方

Cloudflareが公表したClef-omniのモデル比較では、Omniは一部の一般・構造化判定で強いが、どの行でも勝つわけではない。

| 公表ベンチマーク | Clef-omni | 比較値 | 受け取り方 |
|---|---:|---:|---|
| Home appliance simulator (case exact) | 69.3 | Clef 83.0 / Flash 97.7 | Omniの大きな弱点。Flashが最良。 |
| When2Call (accuracy) | 63.3 | Jev 81.0 | Jevが17.7pt高い。 |
| BRIGHT (nDCG@10) | 42.0 | Jev 47.5 / Clef 45.9 | 検索・関連度行はOmniが最良でない。 |
| PhishNChips (accuracy) | 73.2 | Clef 79.6 / Jev 62.5 | Clefが6.4pt高い。 |
| RAGTruth (hallucination F1) | 42.0 | Clef 79.4 / Jev 76.5 | Omniの弱いタスク例。 |
| Invoice processing (exact actions) | 60.2 | Clef 64.7 / Jev 61.8 | 実業務workflow評価でもClefが上。 |
| Agent trace observability (primary action) | 65.8 | Flash 69.8 / Jev 71.6 | Omniが最良でない。 |

数値はCloudflare/Hugging Faceに掲載されたDecision Index 0.2.1およびTypeSafe Evalsの公表値で、親担当の業務データでの実測ではない。記事とモデルカードに試験データ・サーバ構成などの再現条件がすべて載っているわけではない。表に音声/動画専用データセットやモダリティ別の正解率は見当たらず、「音声/動画を扱える」ことと「音声/動画判断の品質が検証済み」は分ける必要がある (表の項目構成からの推定)。

記事が示すOmniの中央値レイテンシはテキスト約130ms、画像約150ms、音声は数百ms、音声付き21秒動画約1.5秒。同記事は計測環境やp95を併記していないため、提供側の報告値として扱う。Clefの約1.7〜2倍の高速化はホストされたClefの話で、約800/3,400/16,000入力tokensについて中央値152/305/1,635ms (p95 351/531/1,805ms)。旧版よりの高速化は主にserve基盤によるもので、新しいClef重みは出ていない。

## Colabなどで動かす担当への条件

本調査ではGPU実行していない。実行担当は、Colabの割当GPUと実空きVRAMを起動後に確認する。Omni公式値は「BF16で約64GB必要、単一H200で確認」のみ。64GBが厳密な必要最小量やColabで確保できることは確認されていない。H200未満のGPU、4bit/8bit量子化、SGLang上部のchat completion例は公式条件の代替として成功扱いしない。`transformers` 5.10.2と`torch` 2.11を基本にし、音声/動画用`av`も準備する。初回検証は固定した一つの入力・質問schema・正解基準を先に決め、公式`load_release_model`経由で確率、生応答、時間、GPU名、ライブラリ版、Hugging Face SHAを残す。

## 参照資料・調査時点

Hugging Faceの`main`は可変なので、この調査では取得したrevisionを記録する。下のshaは2026-10-10にHub APIから取得。

| ID | 一次資料 | 2026-10-10確認内容 |
|---|---|---|
| S1 | [Cloudflare発表記事](https://blog.cloudflare.com/clef-faster-cheaper-multimodal/) | 2026-10-09。Omniの構成・公式値、Flash価格/hosted contextの変更、Clef高速化、既知のベンチマーク表。 |
| S2 | [Workers AI: clef](https://developers.cloudflare.com/workers-ai/models/clef/) | context 65,536、$0.24/M input、現行Parameters。 |
| S3 | [Workers AI: clef-flash](https://developers.cloudflare.com/workers-ai/models/clef-flash/) | context 24,576、$0.038/M input、現行Parameters。 |
| S4 | [Workers AI: clef-omni](https://developers.cloudflare.com/workers-ai/models/clef-omni/) | context 64,000、$0.15/M input、音声/動画と制限・token化。 |
| S5 | [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) | Neurons、無料枠と超過課金の共通条件。 |
| S6 | [Cloudflare/clef](https://huggingface.co/Cloudflare/clef/tree/0b331204bb13fbd2ca93a64df1956f5b55478ce5) | revision `0b331204bb13fbd2ca93a64df1956f5b55478ce5`。backbone/head、正式推論コード、ライセンス、カードのベンチマーク。 |
| S7 | [Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash/tree/8b2e5fd17c09fd49bc2880b805d5323ec7ff4ff3) | revision `8b2e5fd17c09fd49bc2880b805d5323ec7ff4ff3`。backbone/head、正式推論コード、ライセンス、context既定値。 |
| S8 | [Cloudflare/clef-omni](https://huggingface.co/Cloudflare/clef-omni/tree/0db1cd2607d76a7bdb2a382f659e7b313079f84b) | revision `0db1cd2607d76a7bdb2a382f659e7b313079f84b`。基盤・約64GB・正式推論経路・SGLang欄・ライセンス・ベンチマーク。 |
| S9 | [SGLang PR #42721](https://github.com/sgl-project/sglang/pull/42721) | 2026-10-09 merge。対象モデル、`/v1/systemone`、試験条件、制約、速度。merge SHA `bd2d73daa5afda6bcad8d479a834f2e70bbe9569`。 |
| S10 | [SGLang Releases](https://github.com/sgl-project/sglang/releases) / [latest release API](https://api.github.com/repos/sgl-project/sglang/releases/latest) | 2026-10-10のAPI応答はv0.5.21、published 2026-10-02。Cloudflare記事の収録予定v0.5.22とはまだ差がある。 |

### 未確認事項

- Clef/Clef-flash hosted APIで`videos`入力が現在受理されるか。現行Cloudflare Parametersは`images`のみだが、overview・HF・発表記事は動画対応を記載。
- Colab Python CLIでH200相当のGPUを割り当てられるか、割当後の空きVRAM、モデルの実起動・推論・メモリ使用量。
- OmniをClefの専用SGLang `/v1/systemone`経路で配信できるか。現行PRはClef/Flash向け、OmniカードはSGLangをcoming soonとしている。
- 発表者のレイテンシとベンチマーク表を独立に再現するための完全な環境・dataset revision・評価script。
