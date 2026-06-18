from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import CategoryDefinition, Chapter, Entity, LayoutSettings, Note, Project


CSV_HEADERS = [
    "record_type",
    "id",
    "parent_id",
    "title",
    "name",
    "category",
    "field_id",
    "field_name",
    "field_type",
    "order",
    "value",
    "data_json",
]


def export_project_csv(project: Project, project_dir: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    rows.append(
        _row(
            "project",
            id=project.id,
            title=project.title,
            name=project.title,
            value=project.synopsis,
            data=project.to_dict(),
        )
    )
    rows.append(_row("layout", id=project.id, parent_id=project.id, name="Maquetacion", data=project.layout.to_dict()))

    for index, chapter in enumerate(project.chapters, start=1):
        rows.append(
            _row(
                "chapter",
                id=chapter.id,
                parent_id=project.id,
                title=chapter.title,
                name=chapter.title,
                order=index,
                value=chapter.body,
                data=chapter.to_dict(),
            )
        )

    for index, note in enumerate(project.notes, start=1):
        rows.append(
            _row(
                "note",
                id=note.id,
                parent_id=project.id,
                title=note.title,
                name=note.title,
                category=note.category,
                order=index,
                value=note.body,
                data=note.to_dict(),
            )
        )

    for index, category in enumerate(project.categories, start=1):
        rows.append(
            _row(
                "category",
                id=category.id,
                parent_id=project.id,
                name=category.name,
                order=index,
                data=category.to_dict(),
            )
        )
        for field_index, field in enumerate(category.fields, start=1):
            rows.append(
                _row(
                    "category_field",
                    id=field.id,
                    parent_id=category.id,
                    name=field.name,
                    field_name=field.name,
                    field_type=field.type,
                    order=field_index,
                    value=_format_options(field.options, field.required),
                    data=field.to_dict(),
                )
            )
        for variant_index, variant in enumerate(category.variants, start=1):
            rows.append(
                _row(
                    "category_variant",
                    id=variant.id,
                    parent_id=category.id,
                    name=variant.name,
                    order=variant_index,
                    data=variant.to_dict(),
                )
            )
            for field_index, field in enumerate(variant.fields, start=1):
                rows.append(
                    _row(
                        "variant_field",
                        id=field.id,
                        parent_id=variant.id,
                        name=field.name,
                        field_name=field.name,
                        field_type=field.type,
                        order=field_index,
                        value=_format_options(field.options, field.required),
                        data=field.to_dict(),
                    )
                )

    categories_by_id = {item.id: item for item in project.categories}
    for index, entity in enumerate(project.entities, start=1):
        category = categories_by_id.get(entity.category_id)
        rows.append(
            _row(
                "entity",
                id=entity.id,
                parent_id=entity.category_id,
                title=entity.name,
                name=entity.name,
                category=category.name if category else "",
                order=index,
                value=entity.summary,
                data=entity.to_dict(),
            )
        )
        for field_row in _entity_field_rows(entity, category):
            rows.append(field_row)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def import_project_csv(csv_path: Path) -> Project:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("El CSV no contiene registros.")

    project_payload = _payload_from_row(_find_first(rows, "project"))
    project = Project.from_dict(project_payload or {})

    layout_payload = _payload_from_row(_find_first(rows, "layout"))
    if layout_payload:
        project.layout = LayoutSettings.from_dict(layout_payload)

    chapter_payloads = [_payload_from_row(row) for row in _rows_of_type(rows, "chapter")]
    chapter_payloads = [payload for payload in chapter_payloads if payload]
    if chapter_payloads:
        project.chapters = [Chapter.from_dict(payload) for payload in chapter_payloads]

    note_payloads = [_payload_from_row(row) for row in _rows_of_type(rows, "note")]
    note_payloads = [payload for payload in note_payloads if payload]
    if note_payloads:
        project.notes = [Note.from_dict(payload) for payload in note_payloads]

    category_payloads = [_payload_from_row(row) for row in _rows_of_type(rows, "category")]
    category_payloads = [payload for payload in category_payloads if payload]
    if category_payloads:
        project.categories = [CategoryDefinition.from_dict(payload) for payload in category_payloads]

    entity_payloads = [_payload_from_row(row) for row in _rows_of_type(rows, "entity")]
    entity_payloads = [payload for payload in entity_payloads if payload]
    if entity_payloads:
        project.entities = [Entity.from_dict(payload) for payload in entity_payloads]

    project.ensure_defaults()
    return project


def _entity_field_rows(entity: Entity, category: CategoryDefinition | None) -> list[dict[str, str]]:
    if not category:
        return []
    rows: list[dict[str, str]] = []
    fields = list(category.fields)
    variant = next((item for item in category.variants if item.id == entity.variant_id), None)
    if variant:
        fields.extend(variant.fields)
    for field_index, definition in enumerate(fields, start=1):
        value = entity.fields.get(definition.id)
        if value in (None, "", []):
            continue
        rows.append(
            _row(
                "entity_field",
                id=f"{entity.id}:{definition.id}",
                parent_id=entity.id,
                name=definition.name,
                field_id=definition.id,
                field_name=definition.name,
                field_type=definition.type,
                order=field_index,
                value=_stringify(value),
                data={
                    "entity_id": entity.id,
                    "field": definition.to_dict(),
                    "value": value,
                },
            )
        )
    return rows


def _row(record_type: str, **fields: object) -> dict[str, str]:
    row = {key: "" for key in CSV_HEADERS}
    row["record_type"] = record_type
    for key, value in fields.items():
        if key == "data":
            row["data_json"] = json.dumps(value, ensure_ascii=False)
            continue
        if key not in row:
            continue
        row[key] = _stringify(value)
    if not row["data_json"]:
        row["data_json"] = json.dumps({}, ensure_ascii=False)
    return row


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Si" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _format_options(options: list[str], required: bool) -> str:
    parts = []
    if required:
        parts.append("obligatorio=si")
    if options:
        parts.append(f"opciones={json.dumps(options, ensure_ascii=False)}")
    return "; ".join(parts)


def _find_first(rows: list[dict[str, str]], record_type: str) -> dict[str, str] | None:
    return next((row for row in rows if row.get("record_type") == record_type), None)


def _rows_of_type(rows: list[dict[str, str]], record_type: str) -> list[dict[str, str]]:
    return [row for row in rows if row.get("record_type") == record_type]


def _payload_from_row(row: dict[str, str] | None) -> dict[str, object]:
    if not row:
        return {}
    data_json = row.get("data_json", "").strip()
    if data_json:
        try:
            payload = json.loads(data_json)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
    return {}

