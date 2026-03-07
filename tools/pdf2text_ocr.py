#!/usr/bin/env python3
"""
画像PDF（スキャン本）からテキストを抽出するOCRツール

NDL OCR Liteを使用。国立国会図書館が開発した高精度日本語OCR。
縦書き自動対応、読み順自動判定、GPU不要。

使い方:
    # 全ページ抽出（OCRで）
    uv run tools/pdf2text_ocr.py "path/to/scanned.pdf"

    # 特定ページのみ
    uv run tools/pdf2text_ocr.py "path/to/scanned.pdf" --pages 1-10

    # ファイルに保存
    uv run tools/pdf2text_ocr.py "path/to/scanned.pdf" --output result.txt

    # JSON出力（座標・信頼度付き）
    uv run tools/pdf2text_ocr.py "path/to/scanned.pdf" --json

前提: ayumu-lab/repos/ndlocr-lite がclone済み＋依存インストール済み
      pip install -r ayumu-lab/repos/ndlocr-lite/requirements.txt
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


NDLOCR_DIR = Path(__file__).parent.parent / "ayumu-lab" / "repos" / "ndlocr-lite"
NDLOCR_OCR = NDLOCR_DIR / "src" / "ocr.py"


def parse_page_range(pages: str, max_page: int) -> list:
    """ページ範囲をパース（例: "1-10,15,20-25"）"""
    indices = []
    for part in pages.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = int(start) - 1
            end = int(end)
            indices.extend(range(start, min(end, max_page)))
        else:
            indices.append(int(part) - 1)
    return sorted(set(indices))


def pdf_to_images(pdf_path: str, output_dir: str, page_indices: list = None, dpi: int = 300) -> list:
    """PDFをページ画像に変換して保存"""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    total_pages = len(pdf)

    if page_indices is None:
        page_indices = list(range(total_pages))

    image_paths = []
    for i in page_indices:
        if i >= total_pages:
            continue
        page = pdf[i]
        bitmap = page.render(scale=dpi / 72)
        pil_image = bitmap.to_pil()

        img_path = os.path.join(output_dir, f"page_{i+1:04d}.png")
        pil_image.save(img_path)
        image_paths.append(img_path)
        print(f"  ページ {i+1}/{total_pages} を画像化", file=sys.stderr)

    pdf.close()
    return image_paths


def run_ndlocr(image_dir: str, output_dir: str) -> None:
    """NDL OCR Liteを実行"""
    cmd = [
        sys.executable,
        str(NDLOCR_OCR),
        "--sourcedir", image_dir,
        "--output", output_dir,
    ]
    print(f"OCR実行中...", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(NDLOCR_DIR / "src"))
    if result.returncode != 0:
        print(f"OCRエラー: {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"NDL OCR failed: {result.stderr}")
    print(result.stdout, file=sys.stderr)


def collect_results(output_dir: str, output_json: bool = False) -> str:
    """OCR結果を収集して返す"""
    txt_files = sorted(Path(output_dir).glob("*.txt"))
    json_files = sorted(Path(output_dir).glob("*.json"))

    if output_json and json_files:
        all_data = []
        for jf in json_files:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
                all_data.append(data)
        return json.dumps(all_data, ensure_ascii=False, indent=2)

    texts = []
    for tf in txt_files:
        with open(tf, "r", encoding="utf-8") as f:
            text = f.read().strip()
            if text:
                texts.append(text)

    return "\n\n".join(texts)


def main():
    parser = argparse.ArgumentParser(
        description="画像PDF（スキャン本）からテキスト抽出（NDL OCR Lite使用）"
    )
    parser.add_argument("pdf_path", help="PDFファイルのパス")
    parser.add_argument("--pages", "-p", help="ページ範囲（例: 1-10,15,20-25）")
    parser.add_argument("--output", "-o", help="出力ファイル")
    parser.add_argument("--json", "-j", action="store_true", help="JSON出力（座標・信頼度付き）")
    parser.add_argument("--dpi", type=int, default=300, help="レンダリングDPI（デフォルト: 300）")

    args = parser.parse_args()

    if not NDLOCR_OCR.exists():
        print("エラー: NDL OCR Liteが見つかりません", file=sys.stderr)
        print("  git clone https://github.com/ndl-lab/ndlocr-lite ayumu-lab/repos/ndlocr-lite", file=sys.stderr)
        sys.exit(1)

    path = Path(args.pdf_path)
    if not path.exists():
        print(f"エラー: ファイルが見つかりません: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(args.pdf_path)
        total_pages = len(pdf)
        pdf.close()
        print(f"総ページ数: {total_pages}", file=sys.stderr)

        page_indices = None
        if args.pages:
            page_indices = parse_page_range(args.pages, total_pages)
            print(f"抽出ページ: {[i+1 for i in page_indices]}", file=sys.stderr)

        with tempfile.TemporaryDirectory() as tmpdir:
            img_dir = os.path.join(tmpdir, "images")
            ocr_dir = os.path.join(tmpdir, "ocr_output")
            os.makedirs(img_dir)
            os.makedirs(ocr_dir)

            # PDF → 画像
            image_paths = pdf_to_images(args.pdf_path, img_dir, page_indices, args.dpi)
            print(f"{len(image_paths)}ページを画像化完了", file=sys.stderr)

            # OCR実行
            run_ndlocr(img_dir, ocr_dir)

            # 結果収集
            result = collect_results(ocr_dir, output_json=args.json)

        # 出力
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"保存: {args.output}", file=sys.stderr)
        else:
            print(result)

    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
