#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import fitz


def load_kids(json_path: Path):
    with json_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("kids", [])


def union_rect(rects):
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[2] for r in rects)
    y1 = max(r[3] for r in rects)
    return [x0, y0, x1, y1]


def overlaps_vertically(a, b, tol=12.0):
    return not (a[3] + tol < b[1] or b[3] + tol < a[1])


def detect_clusters(kids, min_images=6, x_gap=24.0, y_gap=24.0):
    image_items = [
        {
            "idx": idx,
            "page": kid.get("page number"),
            "bbox": kid.get("bounding box"),
        }
        for idx, kid in enumerate(kids)
        if kid.get("type") == "image" and kid.get("bounding box")
    ]

    by_page = {}
    for item in image_items:
        by_page.setdefault(item["page"], []).append(item)

    clusters = []
    for page, items in by_page.items():
        items = sorted(items, key=lambda x: (-x["bbox"][1], x["bbox"][0]))
        current = []
        current_bbox = None

        for item in items:
            bbox = item["bbox"]
            if not current:
                current = [item]
                current_bbox = bbox[:]
                continue

            cx0, cy0, cx1, cy1 = current_bbox
            ix0, iy0, ix1, iy1 = bbox
            near_x = ix0 <= cx1 + x_gap and ix1 >= cx0 - x_gap
            near_y = iy0 <= cy1 + y_gap and iy1 >= cy0 - y_gap
            same_band = overlaps_vertically(current_bbox, bbox, tol=y_gap)

            if (near_x and near_y) or same_band:
                current.append(item)
                current_bbox = union_rect([current_bbox, bbox])
            else:
                if len(current) >= min_images:
                    clusters.append({"page": page, "items": current[:]})
                current = [item]
                current_bbox = bbox[:]

        if len(current) >= min_images:
            clusters.append({"page": page, "items": current[:]})

    return clusters


def nearby_label_boxes(kids, page, cluster_bbox):
    x0, y0, x1, y1 = cluster_bbox
    labels = []
    captions = []

    for kid in kids:
        if kid.get("page number") != page or not kid.get("bounding box"):
            continue

        bbox = kid["bounding box"]
        content = (kid.get("content") or "").strip()
        ktype = kid.get("type")
        if not content:
            continue

        bx0, by0, bx1, by1 = bbox
        width = bx1 - bx0
        height = by1 - by0

        top_band = by0 >= y1 - 4 and by1 <= y1 + 40 and bx0 >= x0 - 24 and bx1 <= x1 + 24
        left_band = bx1 <= x0 + 4 and bx0 >= x0 - 40 and by0 >= y0 - 12 and by1 <= y1 + 12
        caption_band = by1 <= y0 + 8 and by0 >= y0 - 80 and bx0 >= x0 - 40 and bx1 <= x1 + 40

        if ktype in {"paragraph", "heading"} and len(content) <= 160 and (top_band or left_band):
            labels.append(bbox)
        if ktype == "caption" or (caption_band and content.lower().startswith("fig.")):
            captions.append(bbox)
        if ktype == "paragraph" and left_band and width < 24 and height > 120:
            labels.append(bbox)

    return labels, captions


def pdf_bbox_to_fitz(page_rect, bbox):
    x0, y0, x1, y1 = bbox
    height = page_rect.height
    return fitz.Rect(x0, height - y1, x1, height - y0)


def crop_cluster(pdf_path: Path, page_number: int, bbox, output_path: Path, dpi=200):
    doc = fitz.open(pdf_path)
    page = doc[page_number - 1]
    clip = pdf_bbox_to_fitz(page.rect, bbox)
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), clip=clip, alpha=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(output_path)
    doc.close()


def main():
    parser = argparse.ArgumentParser(description="Detect and crop composite figures from a PDF/json pair.")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--min-images", type=int, default=6)
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    json_path = Path(args.json)
    out_dir = Path(args.out_dir)

    kids = load_kids(json_path)
    clusters = detect_clusters(kids, min_images=args.min_images)
    if not clusters:
        print("No composite figure clusters detected.")
        return

    for n, cluster in enumerate(clusters, start=1):
        page = cluster["page"]
        image_boxes = [item["bbox"] for item in cluster["items"]]
        cluster_bbox = union_rect(image_boxes)
        labels, captions = nearby_label_boxes(kids, page, cluster_bbox)
        final_bbox = union_rect([cluster_bbox, *labels])
        out_path = out_dir / f"page-{page}-composite-{n}.png"
        crop_cluster(pdf_path, page, final_bbox, out_path, dpi=args.dpi)
        print(
            json.dumps(
                {
                    "page": page,
                    "image_count": len(image_boxes),
                    "cluster_bbox": cluster_bbox,
                    "label_count": len(labels),
                    "caption_count": len(captions),
                    "final_bbox": final_bbox,
                    "output": str(out_path),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
