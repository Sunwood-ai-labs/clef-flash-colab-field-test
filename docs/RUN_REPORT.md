# Cloudflare CLEF 実行報告

実行日: 2026-10-10（日本時間）

## 実測結果

Cloudflare/clef-flash を revision `8b2e5fd17c09fd49bc2880b805d5323ec7ff4ff3` に固定し、公式 `joint_schema_model.py` の `load_release_model` と `systemone` を Google Colab CLI から実行した。A100-SXM4-40GB 上の BF16 実行で、固定した2ケースは両方とも合格した。

| ケース | 判定結果 | 入力token | 推論時間 | 基準 |
|---|---|---:|---:|---|
| `text-invoice-01` | `status=overdue`、`large=0.9738`（status confidence `0.9729`） | 260 | 1.901秒 | 合格 |
| `image-hand-holding-candy-01` | `hand_holding_candy=0.9716` | 927 | 2.443秒 | 合格 |

画像は固定JPEG（4032×3024、SHA-256 `FC417C899E94F8DF465B7541C5A70F0EEBB85C414D06345F0B290C061ECCC84C`）を Pillow 11.3.0 で RGB 化し、LANCZOS で1024×768へ縮小して入力した。処理後RGBのSHA-256は `0896B9D2D2224E08AEF571D00DBF2F42B80F1B6366984DAC1489558BF94264F9`。

モデル取得49.144秒、公式ローダー20.136秒、2ケースを含むrun全体74.252秒。実行環境は Python 3.13.15、PyTorch 2.11.0+cu130、Transformers 5.10.2、Pillow 11.3.0、Colab CLI 0.7.2。ロード後のCUDA割当は19,063,236,096 bytes、予約量は19,088,277,504 bytes。すべてのモデルparameterが `cuda:0` のBF16であることを結果JSONに記録した。

HFの固定revision配下は期待されたモデルファイル17個・19,083,378,312 bytesに対し、Colab上のローカルディレクトリ全体はキャッシュ情報を含む54ファイル・19,083,383,439 bytesとなった。モデル本体のrevisionと公式コードSHA-256は固定契約に一致し、ローダーが実際に完了した。

## L4失敗と復旧

先行したL4の単独ロードは `load_release_model` 内でCUDA OOMとなり、ケース推論には到達しなかった。ログではL4総量22.03 GiB、空き4.02 GiBの状態でTransformersのallocator warmupが17.23 GiBを追加要求し、既にPyTorchが17.76 GiBを使用していた。CLIタイムアウトとなった最初の呼び出しはsnapshot取得中で、ロード呼び出しはありません。次の実行で公式ロードは一度だけ行われており、二重ロードではない。

元のL4契約は [contract-l4-preregistered.json](../experiment/contract-l4-preregistered.json) に保全した。A100への変更は [contract.json](../experiment/contract.json) revision 2 に追記し、model revision、ケース入力、正解条件、前処理、公式推論経路は変更していない。L4の失敗JSONとイベントも別ファイルに残した。

## Omniの実行可否

[公式Clef-Omniモデルカード](https://huggingface.co/Cloudflare/clef-omni)は、BF16 backboneに約64GBのGPUメモリが必要で、単一H200での確認を記載している。実際に確保したA100は40GBだった。Colab CLIでH100を要求したが、backendは「quota or entitlement」がないとして拒否した（[割当ログ](../results/h100-request.log)）。Omniは未実行であり、重み量子化や別モデルへの置き換えは行っていない。追加購入・プラン変更もしていない。

作業用A100の停止要求は404 Not Foundで返ったが、その後の利用状況一覧ではA100はなく、残る1件は既存の不明L4割当だったため触れていない。最終確認時の残高は217.44 CU、利用レートは1.54 CU/時、稼働割当はその1件だった。H100要求は割当作成前に拒否されており、新規購入・プラン変更はない。

## 証拠ファイル

- 最終結果と実行環境: [run-result.json](../results/run-result.json)
- 生回答: [text-invoice-01.json](../results/raw-responses/text-invoice-01.json)、[image-hand-holding-candy-01.json](../results/raw-responses/image-hand-holding-candy-01.json)
- 時系列イベント: [run-events-a100.jsonl](../results/run-events-a100.jsonl)
- L4失敗結果: [run-result-l4-failure.json](../results/run-result-l4-failure.json)
- L4イベント: [run-events-l4.jsonl](../results/run-events-l4.jsonl)
- A100契約SHA-256: `E9ECA29B90B6CB54681F8134CE2FCB761EDE0363C95017F80339E24BAC889ADE`
- 最終結果JSON SHA-256: `63ECF66F92E18A89DBDA8C5DEF3D141BA95689A39CA415B037DB3A001B9083B0`

モデルカード: [Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash)、[固定revision](https://huggingface.co/Cloudflare/clef-flash/tree/8b2e5fd17c09fd49bc2880b805d5323ec7ff4ff3)。画像出典: [Hugging Face documentation image](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/p-blog/candy.JPG)。

## 実行上の注意

TransformersからQwen 3.5 docstring診断が出力され、`flash-linear-attention` が未導入のためPyTorch実装へfallbackした。これは推論を止めず、2ケースとも完了した。速度値はこのColab A100環境・この固定入力での実測であり、一般的な性能比較ではない。

## 公開にあたっての変更

契約JSONと結果JSONに含まれていたローカルのパス（Colab CLIの設定ファイル、作業フォルダ）は置き換えた。そのため、このリポジトリの `experiment/contract.json` のSHA-256は、上の「A100契約SHA-256」と一致しない。実行ログの全文は含めていない。
