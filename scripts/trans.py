#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import opendataloader_pdf

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from composite_figure_crop import crop_cluster, detect_clusters, load_kids, nearby_label_boxes, union_rect


def ensure_workspace(vault: Path):
    thesis = vault / "thesis"
    paths = {
        "pdf": thesis / "pdf",
        "fin": thesis / "fin",
        "trn": thesis / "trn",
        "state": thesis / "trn" / ".paper-translate",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def unique_path(path: Path):
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def discover_pdfs(pdf_dir: Path, explicit_pdf: str | None):
    if explicit_pdf:
        pdf = Path(explicit_pdf).expanduser()
        if not pdf.is_absolute():
            pdf = Path.cwd() / pdf
        return [pdf.resolve()]
    return sorted(pdf_dir.glob("*.pdf"))


def extract_pdf(pdf_path: Path):
    output_dir = Path("/tmp") / f"paper-translate-{pdf_path.stem}-{int(time.time())}"
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("JAVA_TOOL_OPTIONS", "-Djava.awt.headless=true")
    opendataloader_pdf.convert(
        input_path=[str(pdf_path)],
        output_dir=str(output_dir),
        format="markdown,json",
        image_output="external",
        image_format="png",
    )

    json_files = sorted(output_dir.glob("*.json"))
    markdown_files = sorted(output_dir.glob("*.md"))
    if not json_files or not markdown_files:
        raise RuntimeError(f"opendataloader-pdf did not create markdown/json files in {output_dir}")

    return {
        "output_dir": output_dir,
        "json": json_files[0],
        "markdown": markdown_files[0],
    }


def copy_images(extract_dir: Path, pdf_stem: str, attachment_dir: Path):
    copied = []
    image_dirs = sorted(extract_dir.glob("*_images"))
    for image_dir in image_dirs:
        target_dir = attachment_dir / "images"
        target_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(image_dir.glob("*")):
            if source.is_file():
                target = unique_path(target_dir / source.name)
                shutil.copy2(source, target)
                copied.append(target)
    return copied


def crop_composites(pdf_path: Path, json_path: Path, attachment_dir: Path):
    kids = load_kids(json_path)
    clusters = detect_clusters(kids)
    outputs = []
    composite_dir = attachment_dir / "composite"

    for index, cluster in enumerate(clusters, start=1):
        page = cluster["page"]
        image_boxes = [item["bbox"] for item in cluster["items"]]
        cluster_bbox = union_rect(image_boxes)
        labels, captions = nearby_label_boxes(kids, page, cluster_bbox)
        final_bbox = union_rect([cluster_bbox, *labels])
        output_path = composite_dir / f"page-{page}-composite-{index}.png"
        crop_cluster(pdf_path, page, final_bbox, output_path)
        outputs.append(
            {
                "page": page,
                "image_count": len(image_boxes),
                "label_count": len(labels),
                "caption_count": len(captions),
                "path": str(output_path),
            }
        )
    return outputs


def obsidian_path(path: Path, vault: Path):
    return path.resolve().relative_to(vault.resolve()).as_posix()


def rewrite_image_links(markdown: str, pdf_stem: str, vault: Path, attachment_dir: Path):
    image_dir = obsidian_path(attachment_dir / "images", vault)
    return markdown.replace(f"{pdf_stem}_images/", f"{image_dir}/")


def write_source_note(pdf_path: Path, extracted_markdown: Path, vault: Path, trn_dir: Path, attachment_dir: Path):
    raw = extracted_markdown.read_text(encoding="utf-8")
    rewritten = rewrite_image_links(raw, pdf_path.stem, vault, attachment_dir)
    source_note = unique_path(trn_dir / f"{pdf_path.stem}__source.md")

    body = f"""---
title: "{pdf_path.stem} source"
source_pdf: "{obsidian_path(pdf_path, vault) if pdf_path.is_relative_to(vault) else str(pdf_path)}"
translation_status: source
tags:
  - paper-translate/source
---

# {pdf_path.stem} Source

> [!info] Translation Task
> 이 파일은 `paper-translate`가 PDF에서 추출한 번역용 소스다.
> 최종 번역 노트는 `{pdf_path.stem} 번역.md` 이름으로 같은 폴더에 작성한다.

{rewritten}
"""
    source_note.write_text(body, encoding="utf-8")
    return source_note


def write_manifest(paths, pdf_path: Path, extract_info, source_note: Path, attachment_dir: Path, composites):
    manifest = {
        "pdf": str(pdf_path),
        "stem": pdf_path.stem,
        "source_note": str(source_note),
        "expected_final_note": str(source_note.parent / f"{pdf_path.stem} 번역.md"),
        "extract_dir": str(extract_info["output_dir"]),
        "json": str(extract_info["json"]),
        "markdown": str(extract_info["markdown"]),
        "attachment_dir": str(attachment_dir),
        "composites": composites,
    }
    manifest_path = paths["state"] / f"{pdf_path.stem}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path, manifest


def prepare_one(vault: Path, paths, pdf_path: Path):
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    extract_info = extract_pdf(pdf_path)
    attachment_dir = paths["trn"] / "_attachments" / pdf_path.stem
    copied_images = copy_images(extract_info["output_dir"], pdf_path.stem, attachment_dir)
    composites = crop_composites(pdf_path, extract_info["json"], attachment_dir)
    source_note = write_source_note(pdf_path, extract_info["markdown"], vault, paths["trn"], attachment_dir)
    manifest_path, manifest = write_manifest(paths, pdf_path, extract_info, source_note, attachment_dir, composites)
    manifest["manifest"] = str(manifest_path)
    manifest["image_count"] = len(copied_images)
    return manifest


def finish_one(paths, pdf_path: Path, final_note: Path | None):
    if final_note is not None and not final_note.exists():
        raise FileNotFoundError(f"Final note does not exist: {final_note}")
    target = unique_path(paths["fin"] / pdf_path.name)
    shutil.move(str(pdf_path), str(target))
    return target


def load_manifest(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Prepare and finish thesis PDF translation jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Extract PDFs and create source notes in thesis/trn")
    prepare.add_argument("--vault", default=str(Path.cwd()), help="Obsidian vault root")
    prepare.add_argument("--pdf", help="Specific PDF to prepare. Defaults to all PDFs in thesis/pdf")

    finish = subparsers.add_parser("finish", help="Move a completed PDF to thesis/fin")
    finish.add_argument("--vault", default=str(Path.cwd()), help="Obsidian vault root")
    finish.add_argument("--manifest", help="Manifest created by prepare")
    finish.add_argument("--pdf", help="PDF path to move")
    finish.add_argument("--final-note", help="Final translated markdown path to check before moving")

    args = parser.parse_args()
    vault = Path(args.vault).expanduser().resolve()
    paths = ensure_workspace(vault)

    if args.command == "prepare":
        pdfs = discover_pdfs(paths["pdf"], args.pdf)
        if not pdfs:
            print(json.dumps({"prepared": [], "message": "No PDFs found in thesis/pdf"}, ensure_ascii=False))
            return
        results = [prepare_one(vault, paths, pdf) for pdf in pdfs]
        print(json.dumps({"prepared": results}, ensure_ascii=False, indent=2))
        return

    if args.command == "finish":
        manifest = load_manifest(Path(args.manifest)) if args.manifest else {}
        pdf = Path(args.pdf or manifest.get("pdf", "")).expanduser()
        final_note_arg = args.final_note or manifest.get("expected_final_note")
        final_note = Path(final_note_arg).expanduser() if final_note_arg else None
        moved_to = finish_one(paths, pdf, final_note)
        print(json.dumps({"moved_to": str(moved_to)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
