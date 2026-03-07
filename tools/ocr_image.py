#!/usr/bin/env python3
"""
画像から日本語テキストを抽出するOCRツール

使用法:
    uv run tools/ocr_image.py <image_path>
    uv run tools/ocr_image.py <image_path> --output result.txt
    uv run tools/ocr_image.py <image_path> --json

依存: yomitoku (uv add yomitoku)
"""

import argparse
import sys
import json
import cv2


def ocr_image(image_path: str) -> dict:
    """画像からテキストを抽出"""
    from yomitoku import DocumentAnalyzer

    # 画像を読み込み
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"画像を読み込めません: {image_path}")

    # CPU版で実行
    analyzer = DocumentAnalyzer(device='cpu')
    result = analyzer(img)

    # 結果を構造化
    doc_result = result[0]
    paragraphs = []
    for para in doc_result.paragraphs:
        paragraphs.append({
            'text': para.contents,
            'bbox': para.box if hasattr(para, 'box') else None
        })

    return {
        'file': image_path,
        'paragraphs': paragraphs,
        'full_text': '\n'.join(p['text'] for p in paragraphs)
    }


def main():
    parser = argparse.ArgumentParser(description='画像から日本語テキストを抽出')
    parser.add_argument('image', help='入力画像ファイル')
    parser.add_argument('--output', '-o', help='出力ファイル（省略時は標準出力）')
    parser.add_argument('--json', action='store_true', help='JSON形式で出力')

    args = parser.parse_args()

    try:
        result = ocr_image(args.image)

        if args.json:
            output = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            output = result['full_text']

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"結果を保存: {args.output}")
        else:
            print(output)

    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"OCRエラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
