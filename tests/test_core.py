import csv
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pescritura.models import Entity, Note, create_empty_project, new_id
from pescritura.csv_export import export_project_csv
from pescritura.pdf_export import build_project_html, export_project_pdf
from pescritura.storage import create_project_backup, create_project_from_csv, load_project, save_project


class CoreTests(unittest.TestCase):
    def test_project_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            project = create_empty_project("Obra de prueba", "Autora")
            project.chapters[0].title = "Capitulo inicial"
            project.chapters[0].body = "Texto de prueba."
            project.notes.append(
                Note(
                    id=new_id("note"),
                    title="Investigacion privada",
                    category="Investigacion",
                    body="Esto no forma parte del manuscrito.",
                )
            )
            category = project.categories[0]
            project.entities.append(
                Entity(
                    id=new_id("entity"),
                    category_id=category.id,
                    name="Personaje",
                    summary="Ficha de prueba",
                    variant_id=category.variants[0].id,
                    fields={category.fields[0].id: "Protagonista"},
                )
            )

            save_project(project, project_dir)
            loaded, loaded_dir = load_project(project_dir)

            self.assertEqual(loaded_dir, project_dir)
            self.assertEqual(loaded.title, "Obra de prueba")
            self.assertEqual(loaded.chapters[0].body, "Texto de prueba.")
            self.assertEqual(loaded.notes[0].title, "Investigacion privada")
            self.assertEqual(loaded.notes[0].category, "Investigacion")
            self.assertEqual(loaded.entities[0].name, "Personaje")

            backup = create_project_backup(project_dir)
            self.assertTrue(backup.exists())
            self.assertEqual(backup.parent, project_dir / "backups")

    def test_notes_are_not_exported_as_manuscript(self) -> None:
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            project = create_empty_project("Separacion", "Autora")
            project.chapters[0].body = "Texto visible en la novela."
            project.notes.append(
                Note(
                    id=new_id("note"),
                    title="Nota privada",
                    body="Detalle que debe quedarse fuera del PDF.",
                )
            )

            rendered = build_project_html(project, project_dir, 520)

            self.assertIn("Texto visible en la novela.", rendered)
            self.assertNotIn("Detalle que debe quedarse fuera del PDF.", rendered)
        self.assertIsNotNone(app)

    def test_pdf_export(self) -> None:
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            project = create_empty_project("PDF de prueba", "Autor")
            project.chapters[0].body = "Primer parrafo.\n\nSegundo parrafo."
            project.layout.include_world_appendix = True
            output = project_dir / "obra.pdf"

            export_project_pdf(project, project_dir, output)

            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 1000)
        self.assertIsNotNone(app)

    def test_csv_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            project = create_empty_project("CSV de prueba", "Autor")
            project.synopsis = "Sinopsis de prueba."
            project.chapters[0].title = "Capitulo 1"
            project.chapters[0].body = "Texto del capitulo."
            project.notes.append(
                Note(
                    id=new_id("note"),
                    title="Nota privada",
                    category="Investigacion",
                    body="Apunte interno.",
                )
            )
            category = project.categories[0]
            project.entities.append(
                Entity(
                    id=new_id("entity"),
                    category_id=category.id,
                    name="Personaje principal",
                    summary="Ficha de prueba",
                    variant_id=category.variants[0].id,
                    fields={category.fields[0].id: "Heroe"},
                )
            )
            output = project_dir / "obra.csv"

            export_project_csv(project, project_dir, output)

            self.assertTrue(output.exists())
            with output.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            record_types = {row["record_type"] for row in rows}
            self.assertIn("project", record_types)
            self.assertIn("chapter", record_types)
            self.assertIn("note", record_types)
            self.assertIn("category", record_types)
            self.assertIn("entity", record_types)
            self.assertIn("entity_field", record_types)
            chapter_row = next(row for row in rows if row["record_type"] == "chapter")
            self.assertEqual(chapter_row["title"], "Capitulo 1")
            self.assertEqual(chapter_row["value"], "Texto del capitulo.")
            note_row = next(row for row in rows if row["record_type"] == "note")
            self.assertEqual(note_row["category"], "Investigacion")

    def test_csv_import_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_project = create_empty_project("Importable", "Autor")
            source_project.synopsis = "Sinopsis."
            source_project.chapters[0].title = "Capitulo 1"
            source_project.chapters[0].body = "Texto."
            source_project.notes.append(
                Note(
                    id=new_id("note"),
                    title="Nota de respaldo",
                    category="Investigacion",
                    body="Contenido.",
                )
            )
            category = source_project.categories[0]
            source_project.entities.append(
                Entity(
                    id=new_id("entity"),
                    category_id=category.id,
                    name="Heroe",
                    summary="Ficha",
                    variant_id=category.variants[0].id,
                    fields={category.fields[0].id: "Protagonista"},
                )
            )

            csv_path = tmp_path / "origen.csv"
            export_project_csv(source_project, tmp_path, csv_path)

            imported_project, imported_dir = create_project_from_csv(csv_path)
            imported_project.chapters[0].body = "Texto."
            save_project(imported_project, imported_dir)
            loaded, loaded_dir = load_project(imported_dir)

            self.assertEqual(loaded_dir, imported_dir)
            self.assertEqual(loaded.title, "Importable")
            self.assertEqual(loaded.chapters[0].title, "Capitulo 1")
            self.assertEqual(loaded.notes[0].title, "Nota de respaldo")
            self.assertEqual(loaded.entities[0].name, "Heroe")
            self.assertEqual(loaded.entities[0].fields[category.fields[0].id], "Protagonista")


if __name__ == "__main__":
    unittest.main()
