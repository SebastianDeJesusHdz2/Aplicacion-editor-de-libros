from __future__ import annotations

import html
import math
import re
from pathlib import Path

from PyQt6.QtCore import QMarginsF, QRectF, QSizeF, Qt, QUrl
from PyQt6.QtGui import (
    QAbstractTextDocumentLayout,
    QColor,
    QFont,
    QFontDatabase,
    QImageReader,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QTextDocument,
)

from .models import CategoryDefinition, Chapter, Entity, FieldDefinition, Project
from .storage import resolve_asset


PAGE_SIZES_MM = {
    "A4": (210.0, 297.0),
    "Carta": (215.9, 279.4),
}


def mm_to_pt(value: float) -> float:
    return value * 72.0 / 25.4


def export_project_pdf(project: Project, project_dir: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    layout = project.layout
    page_width_mm, page_height_mm = PAGE_SIZES_MM.get(layout.page_size, PAGE_SIZES_MM["A4"])
    page_width = mm_to_pt(page_width_mm)
    page_height = mm_to_pt(page_height_mm)
    margins = {
        "top": mm_to_pt(float(layout.margin_top_mm)),
        "right": mm_to_pt(float(layout.margin_right_mm)),
        "bottom": mm_to_pt(float(layout.margin_bottom_mm)),
        "left": mm_to_pt(float(layout.margin_left_mm)),
    }
    content_width = page_width - margins["left"] - margins["right"]
    content_height = page_height - margins["top"] - margins["bottom"]
    if content_width < 180 or content_height < 240:
        raise ValueError("Los margenes dejan un area de pagina demasiado pequena.")

    html_text = build_project_html(project, project_dir, content_width)
    document = QTextDocument()
    document.setDefaultFont(QFont(_font_family(project.layout.font_family), int(project.layout.font_size_pt)))
    document.setPageSize(QSizeF(content_width, content_height))
    document.setHtml(html_text)

    writer = QPdfWriter(str(output_path))
    writer.setCreator("Pescritura")
    writer.setTitle(project.title)
    writer.setResolution(72)
    writer.setPageSize(_qt_page_size(layout.page_size))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)

    painter = QPainter(writer)
    if not painter.isActive():
        raise RuntimeError("No se pudo iniciar el renderizado del PDF.")
    page_count = max(1, math.ceil(document.size().height() / content_height))
    try:
        for page_index in range(page_count):
            if page_index:
                writer.newPage()
            _draw_page(
                painter=painter,
                document=document,
                project=project,
                page_index=page_index,
                page_count=page_count,
                page_width=page_width,
                page_height=page_height,
                content_width=content_width,
                content_height=content_height,
                margins=margins,
            )
    finally:
        painter.end()
    return output_path


def build_project_html(project: Project, project_dir: Path, content_width: float) -> str:
    layout = project.layout
    family = html.escape(_font_family(layout.font_family))
    align = layout.align if layout.align in {"left", "right", "center", "justify"} else "justify"
    parts = [
        "<html><head><meta charset='utf-8'>",
        "<style>",
        f"body {{ font-family: '{family}'; font-size: {int(layout.font_size_pt)}pt; color: #111; }}",
        f"p {{ line-height: {float(layout.line_height):.2f}; margin: 0 0 {int(layout.paragraph_spacing_pt)}pt 0; text-align: {align}; }}",
        "h1 { font-size: 24pt; margin: 0 0 18pt 0; font-weight: 700; }",
        "h2 { font-size: 18pt; margin: 18pt 0 10pt 0; font-weight: 700; }",
        "h3 { font-size: 13pt; margin: 12pt 0 6pt 0; font-weight: 700; }",
        ".muted { color: #555; }",
        ".title-page { text-align: center; margin-top: 190pt; }",
        ".title-page h1 { font-size: 34pt; margin-bottom: 20pt; }",
        ".cover-image { text-align: center; margin: 0 0 32pt 0; }",
        ".toc-entry { margin-bottom: 6pt; }",
        ".chapter { page-break-before: always; }" if layout.chapter_starts_new_page else "",
        ".figure { text-align: center; margin: 14pt 0 18pt 0; }",
        ".field-name { font-weight: 700; }",
        "</style></head><body>",
    ]
    if layout.include_title_page:
        cover = image_tag(project_dir, layout.cover_image, content_width, css_class="cover-image") if layout.cover_image else ""
        parts.extend(
            [
                "<div class='title-page'>",
                cover,
                f"<h1>{html.escape(project.title)}</h1>",
                f"<p class='muted'>{html.escape(project.author)}</p>" if project.author else "",
                "</div>",
            ]
        )
    if project.synopsis:
        parts.extend(["<h1>Sinopsis</h1>", paragraphs_to_html(project.synopsis)])
    if layout.include_toc:
        parts.append("<h1>Indice</h1>")
        for chapter in project.chapters:
            parts.append(f"<p class='toc-entry'>{html.escape(chapter.title)}</p>")
    for chapter in project.chapters:
        parts.append(chapter_to_html(chapter, project_dir, content_width, layout.include_chapter_images))
    if layout.include_world_appendix:
        parts.append(world_appendix_to_html(project, project_dir, content_width))
    parts.append("</body></html>")
    return "\n".join(item for item in parts if item)


def chapter_to_html(chapter: Chapter, project_dir: Path, content_width: float, include_images: bool = True) -> str:
    parts = [f"<div class='chapter'><h1>{html.escape(chapter.title)}</h1>"]
    if include_images and chapter.images:
        for image in chapter.images:
            parts.append(image_tag(project_dir, image, content_width))
    parts.append(paragraphs_to_html(chapter.body))
    parts.append("</div>")
    return "\n".join(parts)


def world_appendix_to_html(project: Project, project_dir: Path, content_width: float) -> str:
    parts = ["<div class='chapter'><h1>Apéndice de mundo</h1>"]
    categories_by_id = {item.id: item for item in project.categories}
    for category in project.categories:
        entities = [item for item in project.entities if item.category_id == category.id]
        if not entities:
            continue
        parts.append(f"<h2>{html.escape(category.name)}</h2>")
        for entity in sorted(entities, key=lambda item: item.name.lower()):
            parts.append(
                entity_to_html(
                    entity,
                    categories_by_id.get(entity.category_id),
                    project_dir,
                    content_width,
                    project.layout.include_entity_photos,
                )
            )
    parts.append("</div>")
    return "\n".join(parts)


def entity_to_html(
    entity: Entity,
    category: CategoryDefinition | None,
    project_dir: Path,
    content_width: float,
    include_photos: bool = True,
) -> str:
    parts = [f"<h3>{html.escape(entity.name)}</h3>"]
    if entity.summary:
        parts.append(paragraphs_to_html(entity.summary))
    if include_photos:
        for photo in entity.photos:
            parts.append(image_tag(project_dir, photo, content_width))
    if not category:
        return "\n".join(parts)
    fields = list(category.fields)
    variant = next((item for item in category.variants if item.id == entity.variant_id), None)
    if variant:
        parts.append(f"<p><span class='field-name'>{html.escape(category.variant_label or 'Tipo')}:</span> {html.escape(variant.name)}</p>")
        fields.extend(variant.fields)
    for definition in fields:
        value = entity.fields.get(definition.id)
        if value in (None, "", []):
            continue
        parts.append(field_value_to_html(definition, value))
    return "\n".join(parts)


def paragraphs_to_html(text: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text or "") if block.strip()]
    if not blocks:
        return "<p></p>"
    rendered = []
    for block in blocks:
        escaped = html.escape(block).replace("\n", "<br>")
        rendered.append(f"<p>{escaped}</p>")
    return "\n".join(rendered)


def field_value_to_html(definition: FieldDefinition, value: object) -> str:
    label = html.escape(definition.name)
    if definition.type == "checkbox":
        rendered = "Si" if bool(value) else "No"
    else:
        rendered = html.escape(str(value))
    if definition.type == "long_text":
        return f"<p><span class='field-name'>{label}:</span></p>{paragraphs_to_html(str(value))}"
    return f"<p><span class='field-name'>{label}:</span> {rendered}</p>"


def image_tag(project_dir: Path, relative_path: str, content_width: float, css_class: str = "figure") -> str:
    path = resolve_asset(project_dir, relative_path)
    if not path.exists():
        return ""
    width = min(max_image_width(path, content_width), content_width)
    url = QUrl.fromLocalFile(str(path)).toString()
    return f"<div class='{css_class}'><img src='{html.escape(url)}' width='{int(width)}'></div>"


def max_image_width(path: Path, content_width: float) -> float:
    reader = QImageReader(str(path))
    size = reader.size()
    if not size.isValid() or size.width() <= 0:
        return content_width
    # Keep small images from exploding too much, while fitting wide references.
    return min(content_width, max(content_width * 0.45, float(size.width())))


def _font_family(preferred: str) -> str:
    families = set(QFontDatabase.families())
    if preferred in families:
        return preferred
    for fallback in ("DejaVu Serif", "Liberation Serif", "Times New Roman", "Serif"):
        if fallback in families:
            return fallback
    return preferred or "Serif"


def _qt_page_size(name: str) -> QPageSize:
    if name == "Carta":
        return QPageSize(QPageSize.PageSizeId.Letter)
    return QPageSize(QPageSize.PageSizeId.A4)


def _draw_page(
    painter: QPainter,
    document: QTextDocument,
    project: Project,
    page_index: int,
    page_count: int,
    page_width: float,
    page_height: float,
    content_width: float,
    content_height: float,
    margins: dict[str, float],
) -> None:
    painter.fillRect(QRectF(0, 0, page_width, page_height), QColor("#ffffff"))
    painter.save()
    painter.translate(margins["left"], margins["top"] - page_index * content_height)
    context = QAbstractTextDocumentLayout.PaintContext()
    context.clip = QRectF(0, page_index * content_height, content_width, content_height)
    document.documentLayout().draw(painter, context)
    painter.restore()

    painter.save()
    painter.setPen(QColor("#666666"))
    small_font = QFont(_font_family(project.layout.font_family), 8)
    painter.setFont(small_font)
    if project.layout.show_header and page_index > 0:
        painter.drawText(
            QRectF(margins["left"], 10, content_width, margins["top"] - 12),
            int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
            project.title,
        )
    if project.layout.show_page_numbers:
        footer = f"{page_index + 1} / {page_count}"
        painter.drawText(
            QRectF(margins["left"], page_height - margins["bottom"] + 7, content_width, margins["bottom"] - 8),
            int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop),
            footer,
        )
    painter.restore()
