---
name: camera
description: "カメラで撮影・画像取得・IPカメラやWebカメラで写真を撮る・PTZ操作・部屋の様子を見るとき → このスキルを読む"
---

# IPカメラ連携スキル

PCに接続されたWebカメラやネットワーク上のIPカメラで写真を撮影する。

## 基本的な使い方

### Webカメラ撮影（take_photo.py）

WSL2環境でも動作。PowerShell経由で自動的にWindows側のカメラにアクセスする。

```bash
# 1枚撮影（デフォルト設定）
uv run .claude/skills/camera/take_photo.py
# → tmp/photo_YYYYMMDD_HHMMSS.jpg に保存される

# 保存先を指定
uv run .claude/skills/camera/take_photo.py output.jpg

# 利用可能なカメラを確認
uv run .claude/skills/camera/take_photo.py --list

# 別のカメラを使う
uv run .claude/skills/camera/take_photo.py --camera 1
```

### PTZカメラ操作（camera.py）

ONVIF対応のPTZカメラを操作する場合：

```bash
# 撮影
uv run tools/camera.py see

# 首振り操作
uv run tools/camera.py look-left 30
uv run tools/camera.py look-right 30
uv run tools/camera.py look-up 20
uv run tools/camera.py look-down 20

# 見回す
uv run tools/camera.py look-around
```

## ユースケース

- **部屋の確認**: カメラで室内の状態を確認
- **作業記録**: 作業環境をキャプチャ
- **見守り**: 定期撮影で安全確認
- **AI Vision**: カメラ入力でAIが周囲を認識

## 技術詳細

- **Webカメラ**: OpenCV (opencv-python) ベース
- **IPカメラ**: ONVIF / RTSP プロトコル
- **対応OS**: Linux、Mac、Windows（WSL2含む）
- **フォーマット**: JPEG
- **ウォームアップ**: 最初の5フレームはスキップ（品質向上）

## トラブルシューティング

### カメラが開けない

```bash
# カメラ一覧確認
uv run .claude/skills/camera/take_photo.py --list

# 別のカメラIDで試す
uv run .claude/skills/camera/take_photo.py --camera 1
```

### 権限エラー（Linux）

```bash
# ユーザーをvideoグループに追加
sudo usermod -a -G video $USER
# 再ログイン必要
```

### WSL環境

WSL2環境ではPowerShell経由で自動的にWindows側のカメラにアクセスする。
追加ツール（CommandCam, ffmpeg）があると高速化できるが、なくても動作する。

## Pythonから使う例

```python
from take_photo import take_photo

# 撮影
photo_path = take_photo("my_photo.jpg")
print(f"保存: {photo_path}")

# デフォルト設定
photo_path = take_photo()  # tmp/photo_*.jpg
```
