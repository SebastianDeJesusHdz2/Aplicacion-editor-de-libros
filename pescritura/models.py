from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


FIELD_TYPES = {
    "text": "Texto corto",
    "long_text": "Texto largo",
    "number": "Numero",
    "date": "Fecha",
    "checkbox": "Si/No",
    "choice": "Opciones",
}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list_from(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


@dataclass
class FieldDefinition:
    id: str
    name: str
    type: str = "text"
    options: list[str] = field(default_factory=list)
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "options": self.options,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldDefinition":
        field_type = data.get("type", "text")
        if field_type not in FIELD_TYPES:
            field_type = "text"
        return cls(
            id=data.get("id") or new_id("field"),
            name=data.get("name") or "Campo",
            type=field_type,
            options=[str(item) for item in _list_from(data.get("options"))],
            required=bool(data.get("required", False)),
        )


@dataclass
class VariantDefinition:
    id: str
    name: str
    fields: list[FieldDefinition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "fields": [item.to_dict() for item in self.fields],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VariantDefinition":
        return cls(
            id=data.get("id") or new_id("variant"),
            name=data.get("name") or "Variante",
            fields=[FieldDefinition.from_dict(item) for item in _list_from(data.get("fields"))],
        )


@dataclass
class CategoryDefinition:
    id: str
    name: str
    variant_label: str = ""
    fields: list[FieldDefinition] = field(default_factory=list)
    variants: list[VariantDefinition] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "variant_label": self.variant_label,
            "fields": [item.to_dict() for item in self.fields],
            "variants": [item.to_dict() for item in self.variants],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CategoryDefinition":
        return cls(
            id=data.get("id") or new_id("category"),
            name=data.get("name") or "Categoria",
            variant_label=data.get("variant_label", ""),
            fields=[FieldDefinition.from_dict(item) for item in _list_from(data.get("fields"))],
            variants=[VariantDefinition.from_dict(item) for item in _list_from(data.get("variants"))],
        )


@dataclass
class Chapter:
    id: str
    title: str
    body: str = ""
    images: list[str] = field(default_factory=list)
    notes: str = ""
    summary: str = ""
    status: str = "Borrador"
    pov: str = ""
    target_words: int = 2500

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "images": self.images,
            "notes": self.notes,
            "summary": self.summary,
            "status": self.status,
            "pov": self.pov,
            "target_words": self.target_words,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chapter":
        return cls(
            id=data.get("id") or new_id("chapter"),
            title=data.get("title") or "Capitulo sin titulo",
            body=data.get("body", ""),
            images=[str(item) for item in _list_from(data.get("images"))],
            notes=data.get("notes", ""),
            summary=data.get("summary", ""),
            status=data.get("status", "Borrador"),
            pov=data.get("pov", ""),
            target_words=int(data.get("target_words", 2500) or 2500),
        )


@dataclass
class Entity:
    id: str
    category_id: str
    name: str
    summary: str = ""
    variant_id: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    photos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category_id": self.category_id,
            "name": self.name,
            "summary": self.summary,
            "variant_id": self.variant_id,
            "fields": self.fields,
            "photos": self.photos,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entity":
        return cls(
            id=data.get("id") or new_id("entity"),
            category_id=data.get("category_id", ""),
            name=data.get("name") or "Entrada sin nombre",
            summary=data.get("summary", ""),
            variant_id=data.get("variant_id", ""),
            fields=dict(data.get("fields") or {}),
            photos=[str(item) for item in _list_from(data.get("photos"))],
        )


@dataclass
class Note:
    id: str
    title: str
    body: str = ""
    category: str = "General"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    pinned: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "category": self.category,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pinned": self.pinned,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Note":
        return cls(
            id=data.get("id") or new_id("note"),
            title=data.get("title") or "Nota sin titulo",
            body=data.get("body", ""),
            category=data.get("category", "General") or "General",
            created_at=data.get("created_at") or now_iso(),
            updated_at=data.get("updated_at") or now_iso(),
            pinned=bool(data.get("pinned", False)),
        )


@dataclass
class LayoutSettings:
    page_size: str = "A4"
    margin_top_mm: float = 22.0
    margin_right_mm: float = 18.0
    margin_bottom_mm: float = 24.0
    margin_left_mm: float = 18.0
    font_family: str = "DejaVu Serif"
    font_size_pt: int = 11
    line_height: float = 1.35
    paragraph_spacing_pt: int = 8
    align: str = "justify"
    include_title_page: bool = True
    include_toc: bool = True
    include_world_appendix: bool = False
    chapter_starts_new_page: bool = True
    show_page_numbers: bool = True
    show_header: bool = True
    cover_image: str = ""
    include_chapter_images: bool = True
    include_entity_photos: bool = True

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutSettings":
        base = cls()
        for key in base.__dict__:
            if key in data:
                setattr(base, key, data[key])
        return base


@dataclass
class Project:
    id: str
    title: str
    author: str = ""
    synopsis: str = ""
    target_words: int = 80000
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    chapters: list[Chapter] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    categories: list[CategoryDefinition] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    layout: LayoutSettings = field(default_factory=LayoutSettings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "synopsis": self.synopsis,
            "target_words": self.target_words,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "chapters": [item.to_dict() for item in self.chapters],
            "notes": [item.to_dict() for item in self.notes],
            "categories": [item.to_dict() for item in self.categories],
            "entities": [item.to_dict() for item in self.entities],
            "layout": self.layout.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        project = cls(
            id=data.get("id") or new_id("project"),
            title=data.get("title") or "Nueva obra",
            author=data.get("author", ""),
            synopsis=data.get("synopsis", ""),
            target_words=int(data.get("target_words", 80000) or 80000),
            created_at=data.get("created_at") or now_iso(),
            updated_at=data.get("updated_at") or now_iso(),
            chapters=[Chapter.from_dict(item) for item in _list_from(data.get("chapters"))],
            notes=[Note.from_dict(item) for item in _list_from(data.get("notes"))],
            categories=[CategoryDefinition.from_dict(item) for item in _list_from(data.get("categories"))],
            entities=[Entity.from_dict(item) for item in _list_from(data.get("entities"))],
            layout=LayoutSettings.from_dict(dict(data.get("layout") or {})),
        )
        project.ensure_defaults()
        return project

    def ensure_defaults(self) -> None:
        if not self.chapters:
            self.chapters.append(Chapter(id=new_id("chapter"), title="Capitulo 1"))
        if not self.categories:
            self.categories.extend(default_categories())
        valid_category_ids = {item.id for item in self.categories}
        if valid_category_ids:
            for entity in self.entities:
                if entity.category_id not in valid_category_ids:
                    entity.category_id = self.categories[0].id

    def category_by_id(self, category_id: str) -> CategoryDefinition | None:
        return next((item for item in self.categories if item.id == category_id), None)

    def chapter_by_id(self, chapter_id: str) -> Chapter | None:
        return next((item for item in self.chapters if item.id == chapter_id), None)

    def note_by_id(self, note_id: str) -> Note | None:
        return next((item for item in self.notes if item.id == note_id), None)

    def entity_by_id(self, entity_id: str) -> Entity | None:
        return next((item for item in self.entities if item.id == entity_id), None)


def default_categories() -> list[CategoryDefinition]:
    personaje = CategoryDefinition(
        id=new_id("category"),
        name="Personajes",
        variant_label="Raza / tipo",
        fields=[
            FieldDefinition(id=new_id("field"), name="Rol narrativo", type="text"),
            FieldDefinition(id=new_id("field"), name="Edad", type="number"),
            FieldDefinition(id=new_id("field"), name="Objetivo", type="long_text"),
            FieldDefinition(id=new_id("field"), name="Conflicto interno", type="long_text"),
        ],
        variants=[
            VariantDefinition(
                id=new_id("variant"),
                name="Humano",
                fields=[
                    FieldDefinition(id=new_id("field"), name="Origen familiar", type="text"),
                    FieldDefinition(id=new_id("field"), name="Oficio", type="text"),
                ],
            ),
            VariantDefinition(
                id=new_id("variant"),
                name="Otra raza",
                fields=[
                    FieldDefinition(id=new_id("field"), name="Rasgos fisicos distintivos", type="long_text"),
                    FieldDefinition(id=new_id("field"), name="Cultura", type="long_text"),
                ],
            ),
        ],
    )
    mundos = CategoryDefinition(
        id=new_id("category"),
        name="Mundos",
        fields=[
            FieldDefinition(id=new_id("field"), name="Reglas naturales", type="long_text"),
            FieldDefinition(id=new_id("field"), name="Historia", type="long_text"),
            FieldDefinition(id=new_id("field"), name="Tono visual", type="text"),
        ],
    )
    lugares = CategoryDefinition(
        id=new_id("category"),
        name="Lugares",
        fields=[
            FieldDefinition(id=new_id("field"), name="Descripcion", type="long_text"),
            FieldDefinition(id=new_id("field"), name="Clima", type="text"),
            FieldDefinition(id=new_id("field"), name="Peligros", type="long_text"),
        ],
    )
    razas = CategoryDefinition(
        id=new_id("category"),
        name="Razas y especies",
        fields=[
            FieldDefinition(id=new_id("field"), name="Apariencia", type="long_text"),
            FieldDefinition(id=new_id("field"), name="Costumbres", type="long_text"),
            FieldDefinition(id=new_id("field"), name="Ventajas", type="long_text"),
            FieldDefinition(id=new_id("field"), name="Debilidades", type="long_text"),
        ],
    )
    return [personaje, mundos, lugares, razas]


def create_empty_project(title: str = "Nueva obra", author: str = "") -> Project:
    project = Project(id=new_id("project"), title=title, author=author)
    project.ensure_defaults()
    return project
