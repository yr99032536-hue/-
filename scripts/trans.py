#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from composite_figure_crop import detect_clusters, load_kids, nearby_label_boxes, pdf_bbox_to_fitz, union_rect

import fitz

WORKSPACE_NAME = "논문"
LEGACY_WORKSPACE_NAME = "thesis"
IMAGE_LINE_RE = re.compile(r"^\s*!\[[^\]]*\]\(<[^>]+>\)\s*$")
LABEL_CELL_RE = re.compile(r"\([A-Za-z]\)\s*.*?(?=(?:\s+\([A-Za-z]\)\s*)|$)")


class PaperTranslateError(RuntimeError):
    pass


def workspace_root(vault: Path):
    preferred = vault / WORKSPACE_NAME
    legacy = vault / LEGACY_WORKSPACE_NAME
    if preferred.exists():
        return preferred
    if legacy.exists():
        return legacy
    return preferred


def ensure_workspace(vault: Path):
    root = workspace_root(vault)
    paths = {
        "root": root,
        "pdf": root / "pdf",
        "fin": root / "fin",
        "trn": root / "trn",
        "state": root / "trn" / ".paper-translate",
    }
    for path in paths.values():
        if isinstance(path, Path):
            path.mkdir(parents=True, exist_ok=True)
    return paths


def validate_workspace(paths):
    for name in ("pdf", "fin", "trn", "state"):
        path = paths[name]
        if not path.exists():
            raise PaperTranslateError(f"Workspace folder is missing: {path}")


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
        resolved = pdf.resolve()
        if not resolved.exists():
            raise PaperTranslateError(f"PDF file not found: {resolved}")
        if resolved.suffix.lower() != ".pdf":
            raise PaperTranslateError(f"Expected a PDF file, got: {resolved}")
        return [resolved]
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if pdfs:
        return pdfs
    raise PaperTranslateError(
        f"No PDFs found in {pdf_dir}. Put files into `{WORKSPACE_NAME}/pdf` and run the command again."
    )


def extract_pdf(pdf_path: Path):
    output_dir = Path(tempfile.gettempdir()) / f"paper-translate-{pdf_path.stem}-{int(time.time())}"
    output_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("JAVA_TOOL_OPTIONS", "-Djava.awt.headless=true")
    try:
        import opendataloader_pdf

        opendataloader_pdf.convert(
            input_path=[str(pdf_path)],
            output_dir=str(output_dir),
            format="markdown,json",
            image_output="external",
            image_format="png",
        )
    except ModuleNotFoundError as exc:
        raise PaperTranslateError(
            "Python package `opendataloader-pdf` is missing. Run `bash scripts/install.sh --vault <vault>` first."
        ) from exc
    except Exception as exc:
        raise PaperTranslateError(
            "PDF extraction failed. Check that Java is installed and `opendataloader-pdf` works in this environment."
        ) from exc

    json_files = sorted(output_dir.glob("*.json"))
    markdown_files = sorted(output_dir.glob("*.md"))
    if not json_files or not markdown_files:
        raise PaperTranslateError(f"Extraction finished, but markdown/json outputs are missing in {output_dir}")

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


def crop_composites(pdf_path: Path, kids: list, attachment_dir: Path):
    clusters = detect_clusters(kids)
    if not clusters:
        return []

    outputs = []
    composite_dir = attachment_dir / "composite"
    doc = fitz.open(pdf_path)

    for index, cluster in enumerate(clusters, start=1):
        page = cluster["page"]
        image_boxes = [item["bbox"] for item in cluster["items"]]
        cluster_bbox = union_rect(image_boxes)
        labels, captions = nearby_label_boxes(kids, page, cluster_bbox)
        final_bbox = union_rect([cluster_bbox, *labels])

        page_obj = doc[page - 1]
        clip = pdf_bbox_to_fitz(page_obj.rect, final_bbox)
        pix = page_obj.get_pixmap(matrix=fitz.Matrix(200 / 72.0, 200 / 72.0), clip=clip, alpha=False)
        output_path = composite_dir / f"page-{page}-composite-{index}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(output_path)

        outputs.append(
            {
                "page": page,
                "image_count": len(image_boxes),
                "label_count": len(labels),
                "caption_count": len(captions),
                "path": str(output_path),
            }
        )

    doc.close()
    return outputs


def obsidian_path(path: Path, vault: Path):
    try:
        return path.resolve().relative_to(vault.resolve()).as_posix()
    except ValueError:
        return str(path)


def rewrite_image_links(markdown: str, pdf_stem: str, vault: Path, attachment_dir: Path):
    image_dir = obsidian_path(attachment_dir / "images", vault)
    return markdown.replace(f"{pdf_stem}_images/", f"{image_dir}/")


def extract_title(kids: list) -> str | None:
    """Extract the paper title from opendataloader JSON kids (first heading level 1)."""
    for kid in kids:
        if kid.get("type") == "heading" and kid.get("heading level") == 1:
            content = (kid.get("content") or "").strip()
            if content:
                return content
    return None


def split_sections(markdown: str) -> list[dict]:
    """Split markdown into sections by ## headings.

    Returns list of {"title": str, "level": int, "content": str}.
    Content before the first ## heading goes into a " preamble" section.
    """
    lines = markdown.split("\n")
    sections: list[dict] = []
    current_title = ""
    current_level = 0
    current_lines: list[str] = []

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            if current_lines or current_title:
                sections.append({
                    "title": current_title,
                    "level": current_level,
                    "content": "\n".join(current_lines),
                })
            current_level = len(m.group(1))
            current_title = m.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines or current_title:
        sections.append({
            "title": current_title,
            "level": current_level,
            "content": "\n".join(current_lines),
        })

    if not sections:
        return [{"title": "", "level": 0, "content": markdown}]

    # preamble(첫 ## 앞 내용)이 있으면 제목 부여
    if sections and sections[0]["level"] == 0 and not sections[0]["title"]:
        first_non_empty = sections[0]["content"].strip()
        if first_non_empty:
            sections[0]["title"] = "preamble"
        else:
            sections.pop(0)

    return sections


def image_kids_with_bbox(kids: list[dict]) -> list[dict]:
    return [
        {
            "page": kid.get("page number"),
            "bbox": kid.get("bounding box"),
        }
        for kid in kids
        if kid.get("type") == "image" and kid.get("bounding box")
    ]


def bboxes_share_row(bboxes: list[list[float]], tol: float = 18.0) -> bool:
    if len(bboxes) < 2:
        return False
    top = max(b[1] for b in bboxes)
    bottom = min(b[3] for b in bboxes)
    return bottom + tol >= top


def extract_label_cells(line: str) -> list[str]:
    return [match.group(0).strip() for match in LABEL_CELL_RE.finditer(line)]


def build_image_table(image_lines: list[str], labels: list[str] | None = None) -> list[str]:
    table = [
        "| " + " | ".join(image_lines) + " |",
        "|" + "|".join([":---:"] * len(image_lines)) + "|",
    ]
    if labels:
        table.append("| " + " | ".join(labels) + " |")
    return table


def apply_image_layout_tables(markdown: str, kids: list[dict]) -> str:
    """Use PDF image bounding boxes to preserve horizontal subfigure rows.

    We rewrite consecutive image blocks that belong to the same visual row into
    markdown tables so Obsidian keeps them horizontal.
    """
    lines = markdown.splitlines()
    image_meta = image_kids_with_bbox(kids)
    image_cursor = 0
    output: list[str] = []
    i = 0

    while i < len(lines):
        if not IMAGE_LINE_RE.match(lines[i]):
            output.append(lines[i])
            i += 1
            continue

        block_start = i
        image_lines: list[str] = []
        image_entries: list[dict] = []

        while i < len(lines) and (not lines[i].strip() or IMAGE_LINE_RE.match(lines[i])):
            if IMAGE_LINE_RE.match(lines[i]):
                meta = image_meta[image_cursor] if image_cursor < len(image_meta) else None
                image_cursor += 1
                image_lines.append(lines[i].strip())
                image_entries.append({"line": lines[i].strip(), "meta": meta})
            i += 1

        if len(image_entries) < 2:
            output.extend(lines[block_start:i])
            continue

        metas = [entry["meta"] for entry in image_entries if entry["meta"]]
        same_page = len({meta["page"] for meta in metas}) == 1 if metas else False
        same_row = len(metas) == len(image_entries) and same_page and bboxes_share_row([meta["bbox"] for meta in metas])
        if not same_row:
            output.extend(lines[block_start:i])
            continue

        image_entries.sort(key=lambda entry: entry["meta"]["bbox"][0])
        label_index = i
        while label_index < len(lines) and not lines[label_index].strip():
            label_index += 1
        labels = extract_label_cells(lines[label_index]) if label_index < len(lines) else []
        use_labels = len(labels) == len(image_entries)

        output.extend(build_image_table([entry["line"] for entry in image_entries], labels if use_labels else None))
        output.append("")
        if use_labels:
            i = label_index + 1

    return "\n".join(output)


def write_source_note(pdf_path: Path, extracted_markdown: Path, vault: Path, trn_dir: Path, attachment_dir: Path, kids: list[dict]):
    raw = extracted_markdown.read_text(encoding="utf-8")
    rewritten = rewrite_image_links(raw, pdf_path.stem, vault, attachment_dir)
    rewritten = apply_image_layout_tables(rewritten, kids)
    sections = split_sections(rewritten)
    source_note = unique_path(trn_dir / f"{pdf_path.stem}__source.md")

    body = f"""---
title: "{pdf_path.stem} source"
source_pdf: "{obsidian_path(pdf_path, vault)}"
translation_status: source
tags:
  - paper-translate/source
---

# {pdf_path.stem} Source

> [!info] Translation Task
> 이 파일은 `paper-translate`가 PDF에서 추출한 번역용 소스다.
> 최종 번역 노트는 manifest의 `expected_final_note` 경로에 작성한다.
> 섹션별로 나누어 번역하고, 번역된 섹션을 순서대로 append 한다.

{rewritten}
"""
    source_note.write_text(body, encoding="utf-8")
    return source_note, sections


def write_manifest(paths, pdf_path: Path, extract_info, source_note: Path, attachment_dir: Path, composites, title: str | None, sections: list[dict]):
    safe_title = (title or pdf_path.stem).replace("/", "-").replace("\\", "-").replace(":", "-")
    expected_note_name = f"{safe_title}.md"

    section_meta = []
    for i, sec in enumerate(sections):
        section_meta.append({
            "index": i,
            "title": sec["title"],
            "level": sec["level"],
            "char_count": len(sec["content"]),
        })

    manifest = {
        "workspace": str(paths["root"]),
        "pdf": str(pdf_path),
        "stem": pdf_path.stem,
        "title": title,
        "source_note": str(source_note),
        "expected_final_note": str(source_note.parent / expected_note_name),
        "extract_dir": str(extract_info["output_dir"]),
        "json": str(extract_info["json"]),
        "markdown": str(extract_info["markdown"]),
        "attachment_dir": str(attachment_dir),
        "composites": composites,
        "sections": section_meta,
        "total_sections": len(sections),
    }
    manifest_path = paths["state"] / f"{pdf_path.stem}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path, manifest


def prepare_one(vault: Path, paths, pdf_path: Path):
    if not pdf_path.exists():
        raise PaperTranslateError(f"PDF file not found: {pdf_path}")

    extract_info = extract_pdf(pdf_path)
    kids = load_kids(extract_info["json"])
    attachment_dir = paths["trn"] / "_attachments" / pdf_path.stem
    copied_images = copy_images(extract_info["output_dir"], pdf_path.stem, attachment_dir)
    composites = crop_composites(pdf_path, kids, attachment_dir)
    title = extract_title(kids)
    source_note, sections = write_source_note(pdf_path, extract_info["markdown"], vault, paths["trn"], attachment_dir, kids)
    manifest_path, manifest = write_manifest(paths, pdf_path, extract_info, source_note, attachment_dir, composites, title, sections)
    manifest["manifest"] = str(manifest_path)
    manifest["image_count"] = len(copied_images)
    return manifest


def finish_one(paths, pdf_path: Path, final_note: Path | None):
    if not pdf_path.exists():
        raise PaperTranslateError(f"PDF file not found for finish step: {pdf_path}")
    if final_note is not None and not final_note.exists():
        raise PaperTranslateError(
            f"Final translated note is missing: {final_note}. Create the translated markdown first, then rerun finish."
        )
    target = unique_path(paths["fin"] / pdf_path.name)
    shutil.move(str(pdf_path), str(target))
    return target


def load_manifest(path: Path):
    if not path.exists():
        raise PaperTranslateError(f"Manifest file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def command_prepare(vault: Path, paths, explicit_pdf: str | None):
    pdfs = discover_pdfs(paths["pdf"], explicit_pdf)
    results = [prepare_one(vault, paths, pdf) for pdf in pdfs]
    return {
        "workspace": str(paths["root"]),
        "prepared": results,
        "message": f"Prepared {len(results)} PDF(s). Translate the generated `__source.md` notes in `{paths['trn']}`.",
    }


def cleanup_extract_dir(manifest: dict):
    extract_dir = manifest.get("extract_dir")
    if extract_dir:
        path = Path(extract_dir)
        if path.exists() and "paper-translate-" in path.name:
            shutil.rmtree(path, ignore_errors=True)


def command_finish(paths, manifest_arg: str | None, pdf_arg: str | None, final_note_arg: str | None):
    manifest = load_manifest(Path(manifest_arg).expanduser()) if manifest_arg else {}
    pdf_value = pdf_arg or manifest.get("pdf")
    if not pdf_value:
        raise PaperTranslateError("Finish requires `--manifest` or `--pdf`.")
    pdf = Path(pdf_value).expanduser()
    final_note_value = final_note_arg or manifest.get("expected_final_note")
    final_note = Path(final_note_value).expanduser() if final_note_value else None
    moved_to = finish_one(paths, pdf, final_note)
    cleanup_extract_dir(manifest)
    return {"workspace": str(paths["root"]), "moved_to": str(moved_to)}


def main():
    parser = argparse.ArgumentParser(description="Prepare and finish paper translation jobs in the Obsidian workspace.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Extract PDFs and create source notes in 논문/trn")
    prepare.add_argument("--vault", default=str(Path.cwd()), help="Obsidian vault root")
    prepare.add_argument("--pdf", help="Specific PDF to prepare. Defaults to all PDFs in 논문/pdf")

    finish = subparsers.add_parser("finish", help="Move a completed PDF to 논문/fin")
    finish.add_argument("--vault", default=str(Path.cwd()), help="Obsidian vault root")
    finish.add_argument("--manifest", help="Manifest created by prepare")
    finish.add_argument("--pdf", help="PDF path to move")
    finish.add_argument("--final-note", help="Final translated markdown path to check before moving")

    args = parser.parse_args()
    vault = Path(args.vault).expanduser().resolve()
    paths = ensure_workspace(vault)
    validate_workspace(paths)

    try:
        if args.command == "prepare":
            sys.stdout.buffer.write(json.dumps(command_prepare(vault, paths, args.pdf), ensure_ascii=False, indent=2).encode("utf-8"))
            sys.stdout.buffer.write(b"\n")
            return

        if args.command == "finish":
            print(json.dumps(command_finish(paths, args.manifest, args.pdf, args.final_note), ensure_ascii=False, indent=2))
            return
    except PaperTranslateError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "command": args.command,
                    "workspace": str(paths["root"]),
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    raise PaperTranslateError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
