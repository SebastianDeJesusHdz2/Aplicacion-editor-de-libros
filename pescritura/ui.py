from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QDate, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QColor, QDoubleValidator, QFont, QIcon, QLinearGradient, QPainter, QPaintEvent, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .models import (
    FIELD_TYPES,
    CategoryDefinition,
    Chapter,
    Entity,
    FieldDefinition,
    LayoutSettings,
    Note,
    Project,
    VariantDefinition,
    new_id,
    now_iso,
)
from .csv_export import export_project_csv
from .pdf_export import build_project_html, export_project_pdf
from .storage import (
    copy_asset,
    create_project_backup,
    create_project_from_csv,
    create_project,
    default_csv_path,
    default_pdf_path,
    ensure_runtime_dirs,
    list_projects,
    load_project,
    resolve_asset,
    save_project,
)


IMAGE_FILTER = "Imagenes (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;Todos los archivos (*)"
CHAPTER_STATUSES = ["Idea", "Borrador", "Revision", "Final"]


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\wáéíóúÁÉÍÓÚñÑüÜ'-]+\b", text or ""))


def percent(value: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, int((value / total) * 100)))


class BackdropWidget(QWidget):
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#16130f"))
        gradient.setColorAt(0.42, QColor("#0f1714"))
        gradient.setColorAt(1.0, QColor("#171017"))
        painter.fillRect(self.rect(), gradient)
        painter.setPen(QColor(255, 244, 220, 13))
        step = 46
        for x in range(0, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            painter.drawLine(0, y, self.width(), y)
        painter.setPen(QColor(111, 191, 176, 42))
        painter.drawLine(0, 82, self.width(), 26)
        painter.setPen(QColor(214, 168, 79, 35))
        painter.drawLine(0, self.height() - 56, self.width(), self.height() - 138)
        painter.setPen(QColor(184, 92, 112, 24))
        painter.drawLine(self.width() // 5, 0, self.width(), self.height())
        super().paintEvent(event)


class StatCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("MutedLabel")
        self.value_label = QLabel("0")
        self.value_label.setObjectName("StatValue")
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("MutedLabel")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def set_values(self, value: str, detail: str = "") -> None:
        self.value_label.setText(value)
        self.detail_label.setText(detail)


class ImagePreviewDialog(QDialog):
    def __init__(self, parent: QWidget | None, image_path: Path):
        super().__init__(parent)
        self.setWindowTitle(image_path.name)
        self.resize(820, 620)
        layout = QVBoxLayout(self)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumSize(640, 460)
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            label.setText("No se pudo cargar la imagen.")
        else:
            label.setPixmap(pixmap.scaled(760, 520, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        path_label = QLabel(str(image_path))
        path_label.setObjectName("MutedLabel")
        path_label.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(label, 1)
        layout.addWidget(path_label)
        layout.addWidget(buttons)


def panel(name: str = "GlassPanel") -> QFrame:
    frame = QFrame()
    frame.setObjectName(name)
    frame.setFrameShape(QFrame.Shape.NoFrame)
    return frame


def small_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QMainWindow {
            background: #11100e;
        }
        QWidget#Backdrop {
            background: transparent;
        }
        QWidget {
            color: #f7f2e8;
            font-family: "Inter", "Segoe UI", "DejaVu Sans", sans-serif;
            font-size: 13px;
        }
        QFrame#GlassPanel, QFrame#HeaderPanel, QFrame#StatCard, QFrame#PreviewPage, QGroupBox {
            background-color: rgba(27, 25, 22, 226);
            border: 1px solid rgba(214, 168, 79, 58);
            border-radius: 8px;
        }
        QFrame#HeaderPanel {
            background-color: rgba(20, 28, 25, 236);
            border-color: rgba(111, 191, 176, 92);
        }
        QFrame#PreviewPage {
            background-color: rgba(250, 247, 239, 248);
            border-color: rgba(255, 244, 220, 120);
        }
        QLabel#AppTitle {
            font-size: 24px;
            font-weight: 700;
            color: #fff8ea;
        }
        QLabel#SectionTitle {
            font-size: 16px;
            font-weight: 700;
            color: #fff4d7;
        }
        QLabel#MutedLabel {
            color: #bfb6a7;
        }
        QLabel#StatValue {
            font-size: 25px;
            font-weight: 700;
            color: #ffffff;
        }
        QLabel#Chip {
            background-color: rgba(111, 191, 176, 58);
            border: 1px solid rgba(111, 191, 176, 120);
            border-radius: 6px;
            padding: 5px 8px;
            color: #dcfff8;
        }
        QGroupBox {
            margin-top: 18px;
            padding: 14px 12px 12px 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #f2d089;
        }
        QTabWidget::pane {
            border: 0;
            top: -1px;
        }
        QTabBar::tab {
            background: rgba(255, 244, 220, 22);
            border: 1px solid rgba(255, 244, 220, 36);
            padding: 9px 16px;
            margin-right: 4px;
            border-top-left-radius: 7px;
            border-top-right-radius: 7px;
        }
        QTabBar::tab:hover {
            background: rgba(111, 191, 176, 42);
        }
        QTabBar::tab:selected {
            background: rgba(111, 191, 176, 82);
            border-color: rgba(150, 225, 211, 150);
        }
        QLineEdit, QTextEdit, QListWidget, QTreeWidget, QComboBox, QSpinBox,
        QDoubleSpinBox, QDateEdit, QFontComboBox, QTextBrowser {
            background-color: rgba(11, 13, 12, 164);
            color: #fff9ec;
            border: 1px solid rgba(255, 244, 220, 48);
            border-radius: 6px;
            padding: 6px;
            selection-background-color: #3b756d;
        }
        QLineEdit:focus, QTextEdit:focus, QListWidget:focus, QTreeWidget:focus,
        QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
        QFontComboBox:focus, QTextBrowser:focus {
            border-color: rgba(214, 168, 79, 160);
        }
        QTextEdit {
            line-height: 1.4;
        }
        QTextBrowser#PdfPreview, QTextBrowser#LibrarySynopsis {
            background-color: #fbf7ed;
            color: #1d1914;
            border-radius: 7px;
            padding: 18px;
        }
        QHeaderView::section {
            background-color: rgba(111, 191, 176, 50);
            color: #fff8ea;
            border: 0;
            border-right: 1px solid rgba(255, 244, 220, 34);
            padding: 6px;
        }
        QTreeWidget {
            alternate-background-color: rgba(255, 244, 220, 10);
        }
        QListWidget::item, QTreeWidget::item {
            padding: 6px;
            min-height: 22px;
        }
        QListWidget::item:hover, QTreeWidget::item:hover {
            background-color: rgba(214, 168, 79, 38);
            border-radius: 5px;
        }
        QListWidget::item:selected, QTreeWidget::item:selected {
            background-color: rgba(111, 191, 176, 120);
            border-radius: 5px;
        }
        QPushButton, QToolButton {
            background-color: rgba(255, 244, 220, 28);
            color: #fff9ec;
            border: 1px solid rgba(255, 244, 220, 52);
            border-radius: 6px;
            padding: 7px 10px;
        }
        QPushButton:hover, QToolButton:hover {
            background-color: rgba(111, 191, 176, 92);
            border-color: rgba(150, 225, 211, 170);
        }
        QPushButton:pressed, QToolButton:pressed {
            background-color: rgba(184, 92, 112, 118);
        }
        QToolBar {
            background-color: rgba(18, 18, 16, 232);
            border: 0;
            spacing: 8px;
            padding: 8px;
        }
        QStatusBar {
            background-color: rgba(18, 18, 16, 232);
            color: #cfc4b5;
        }
        QSplitter::handle {
            background-color: rgba(214, 168, 79, 34);
        }
        QScrollArea {
            border: 0;
            background: transparent;
        }
        QCheckBox {
            spacing: 8px;
        }
        QProgressBar {
            background-color: rgba(255, 244, 220, 24);
            border: 1px solid rgba(255, 244, 220, 44);
            border-radius: 5px;
            height: 12px;
            text-align: center;
            color: transparent;
        }
        QProgressBar::chunk {
            background-color: #6fbfb0;
            border-radius: 4px;
        }
        """
    )


class FieldDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, field: FieldDefinition | None = None):
        super().__init__(parent)
        self.setWindowTitle("Campo")
        self.field = copy.deepcopy(field) if field else FieldDefinition(id=new_id("field"), name="Nuevo campo")
        self.name_edit = QLineEdit(self.field.name)
        self.type_combo = QComboBox()
        for key, label in FIELD_TYPES.items():
            self.type_combo.addItem(label, key)
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(self.field.type)))
        self.required_check = QCheckBox("Obligatorio")
        self.required_check.setChecked(self.field.required)
        self.options_edit = QLineEdit(", ".join(self.field.options))
        self.options_edit.setPlaceholderText("Ej: Noble, Mercenario, Hechicero")

        form = QFormLayout()
        form.addRow("Nombre", self.name_edit)
        form.addRow("Tipo", self.type_combo)
        form.addRow("", self.required_check)
        form.addRow("Opciones", self.options_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.type_combo.currentIndexChanged.connect(self._toggle_options)
        self._toggle_options()

    def _toggle_options(self, *_args: Any) -> None:
        self.options_edit.setEnabled(self.type_combo.currentData() == "choice")

    def accept(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Campo incompleto", "El campo necesita un nombre.")
            return
        self.field.name = name
        self.field.type = self.type_combo.currentData()
        self.field.required = self.required_check.isChecked()
        self.field.options = [item.strip() for item in self.options_edit.text().split(",") if item.strip()]
        super().accept()


class SchemaDialog(QDialog):
    def __init__(self, parent: QWidget | None, categories: list[CategoryDefinition]):
        super().__init__(parent)
        self.setWindowTitle("Categorias y campos del mundo")
        self.resize(980, 620)
        self.categories = copy.deepcopy(categories)
        self.current_category_id = ""
        self.current_variant_id = ""
        self._loading = False

        self.category_list = QListWidget()
        self.category_name = QLineEdit()
        self.variant_label = QLineEdit()
        self.fields_tree = QTreeWidget()
        self.fields_tree.setHeaderLabels(["Campo", "Tipo", "Opciones", "Obligatorio"])
        self.variant_list = QListWidget()
        self.variant_fields_tree = QTreeWidget()
        self.variant_fields_tree.setHeaderLabels(["Campo", "Tipo", "Opciones", "Obligatorio"])

        root = QHBoxLayout(self)
        left = panel()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Categorias"))
        left_layout.addWidget(self.category_list)
        cat_buttons = QHBoxLayout()
        add_cat = small_button("Categoria +")
        del_cat = small_button("Eliminar")
        cat_buttons.addWidget(add_cat)
        cat_buttons.addWidget(del_cat)
        left_layout.addLayout(cat_buttons)
        root.addWidget(left, 1)

        right = panel()
        right_layout = QVBoxLayout(right)
        form = QFormLayout()
        form.addRow("Nombre", self.category_name)
        form.addRow("Etiqueta de variante", self.variant_label)
        right_layout.addLayout(form)

        right_layout.addWidget(QLabel("Campos generales"))
        right_layout.addWidget(self.fields_tree, 1)
        field_buttons = QHBoxLayout()
        add_field = small_button("Campo +")
        edit_field = small_button("Editar")
        del_field = small_button("Eliminar")
        field_buttons.addWidget(add_field)
        field_buttons.addWidget(edit_field)
        field_buttons.addWidget(del_field)
        right_layout.addLayout(field_buttons)

        variant_box = QGroupBox("Variantes por raza/tipo")
        variant_layout = QGridLayout(variant_box)
        variant_layout.addWidget(self.variant_list, 0, 0, 1, 3)
        add_variant = small_button("Variante +")
        rename_variant = small_button("Renombrar")
        del_variant = small_button("Eliminar")
        variant_layout.addWidget(add_variant, 1, 0)
        variant_layout.addWidget(rename_variant, 1, 1)
        variant_layout.addWidget(del_variant, 1, 2)
        variant_layout.addWidget(self.variant_fields_tree, 2, 0, 1, 3)
        add_variant_field = small_button("Campo +")
        edit_variant_field = small_button("Editar")
        del_variant_field = small_button("Eliminar")
        variant_layout.addWidget(add_variant_field, 3, 0)
        variant_layout.addWidget(edit_variant_field, 3, 1)
        variant_layout.addWidget(del_variant_field, 3, 2)
        right_layout.addWidget(variant_box, 2)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)
        root.addWidget(right, 3)

        add_cat.clicked.connect(self.add_category)
        del_cat.clicked.connect(self.delete_category)
        add_field.clicked.connect(lambda: self.add_field(False))
        edit_field.clicked.connect(lambda: self.edit_field(False))
        del_field.clicked.connect(lambda: self.delete_field(False))
        add_variant.clicked.connect(self.add_variant)
        rename_variant.clicked.connect(self.rename_variant)
        del_variant.clicked.connect(self.delete_variant)
        add_variant_field.clicked.connect(lambda: self.add_field(True))
        edit_variant_field.clicked.connect(lambda: self.edit_field(True))
        del_variant_field.clicked.connect(lambda: self.delete_field(True))
        self.category_list.currentItemChanged.connect(self.on_category_selected)
        self.variant_list.currentItemChanged.connect(self.on_variant_selected)
        self.category_name.textEdited.connect(self.update_current_category)
        self.variant_label.textEdited.connect(self.update_current_category)

        self.refresh_categories()
        if self.categories:
            self.category_list.setCurrentRow(0)

    def refresh_categories(self) -> None:
        self._loading = True
        self.category_list.clear()
        for category in self.categories:
            item = QListWidgetItem(category.name)
            item.setData(Qt.ItemDataRole.UserRole, category.id)
            self.category_list.addItem(item)
        self._loading = False

    def selected_category(self) -> CategoryDefinition | None:
        return next((item for item in self.categories if item.id == self.current_category_id), None)

    def selected_variant(self) -> VariantDefinition | None:
        category = self.selected_category()
        if not category:
            return None
        return next((item for item in category.variants if item.id == self.current_variant_id), None)

    def on_category_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        if self._loading:
            return
        self.current_category_id = current.data(Qt.ItemDataRole.UserRole) if current else ""
        self.load_category()

    def load_category(self) -> None:
        category = self.selected_category()
        self._loading = True
        self.category_name.setText(category.name if category else "")
        self.variant_label.setText(category.variant_label if category else "")
        self.fields_tree.clear()
        self.variant_list.clear()
        self.variant_fields_tree.clear()
        self.current_variant_id = ""
        if category:
            self.fill_field_tree(self.fields_tree, category.fields)
            for variant in category.variants:
                item = QListWidgetItem(variant.name)
                item.setData(Qt.ItemDataRole.UserRole, variant.id)
                self.variant_list.addItem(item)
            if category.variants:
                self.current_variant_id = category.variants[0].id
                self.variant_list.setCurrentRow(0)
                self.fill_field_tree(self.variant_fields_tree, category.variants[0].fields)
        self._loading = False

    def on_variant_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None = None) -> None:
        if self._loading:
            return
        self.current_variant_id = current.data(Qt.ItemDataRole.UserRole) if current else ""
        self.refresh_variant_fields()

    def refresh_variant_fields(self) -> None:
        self.variant_fields_tree.clear()
        variant = self.selected_variant()
        if variant:
            self.fill_field_tree(self.variant_fields_tree, variant.fields)

    def update_current_category(self, *_args: Any) -> None:
        if self._loading:
            return
        category = self.selected_category()
        if not category:
            return
        category.name = self.category_name.text().strip() or category.name
        category.variant_label = self.variant_label.text().strip()
        current = self.category_list.currentItem()
        if current:
            current.setText(category.name)

    def fill_field_tree(self, tree: QTreeWidget, fields: list[FieldDefinition]) -> None:
        tree.clear()
        for definition in fields:
            item = QTreeWidgetItem(
                [
                    definition.name,
                    FIELD_TYPES.get(definition.type, definition.type),
                    ", ".join(definition.options),
                    "Si" if definition.required else "No",
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, definition.id)
            tree.addTopLevelItem(item)
        tree.resizeColumnToContents(0)

    def add_category(self) -> None:
        name, ok = QInputDialog.getText(self, "Nueva categoria", "Nombre")
        if not ok or not name.strip():
            return
        category = CategoryDefinition(id=new_id("category"), name=name.strip())
        self.categories.append(category)
        self.refresh_categories()
        self.category_list.setCurrentRow(self.category_list.count() - 1)

    def delete_category(self) -> None:
        category = self.selected_category()
        if not category or len(self.categories) <= 1:
            QMessageBox.warning(self, "Categoria requerida", "Debe existir al menos una categoria.")
            return
        self.categories = [item for item in self.categories if item.id != category.id]
        self.current_category_id = ""
        self.refresh_categories()
        self.category_list.setCurrentRow(0)

    def current_field_list(self, variant: bool) -> list[FieldDefinition] | None:
        if variant:
            selected = self.selected_variant()
            return selected.fields if selected else None
        category = self.selected_category()
        return category.fields if category else None

    def current_field_tree(self, variant: bool) -> QTreeWidget:
        return self.variant_fields_tree if variant else self.fields_tree

    def add_field(self, variant: bool) -> None:
        fields = self.current_field_list(variant)
        if fields is None:
            return
        dialog = FieldDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        fields.append(dialog.field)
        if variant:
            self.refresh_variant_fields()
        else:
            self.fill_field_tree(self.fields_tree, fields)

    def edit_field(self, variant: bool) -> None:
        fields = self.current_field_list(variant)
        tree = self.current_field_tree(variant)
        current = tree.currentItem()
        if fields is None or not current:
            return
        field_id = current.data(0, Qt.ItemDataRole.UserRole)
        definition = next((item for item in fields if item.id == field_id), None)
        if not definition:
            return
        dialog = FieldDialog(self, definition)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        index = fields.index(definition)
        fields[index] = dialog.field
        if variant:
            self.refresh_variant_fields()
        else:
            self.fill_field_tree(self.fields_tree, fields)

    def delete_field(self, variant: bool) -> None:
        fields = self.current_field_list(variant)
        tree = self.current_field_tree(variant)
        current = tree.currentItem()
        if fields is None or not current:
            return
        field_id = current.data(0, Qt.ItemDataRole.UserRole)
        fields[:] = [item for item in fields if item.id != field_id]
        if variant:
            self.refresh_variant_fields()
        else:
            self.fill_field_tree(tree, fields)

    def add_variant(self) -> None:
        category = self.selected_category()
        if not category:
            return
        name, ok = QInputDialog.getText(self, "Nueva variante", "Nombre")
        if not ok or not name.strip():
            return
        category.variants.append(VariantDefinition(id=new_id("variant"), name=name.strip()))
        self.load_category()
        self.variant_list.setCurrentRow(self.variant_list.count() - 1)

    def rename_variant(self) -> None:
        variant = self.selected_variant()
        if not variant:
            return
        name, ok = QInputDialog.getText(self, "Renombrar variante", "Nombre", text=variant.name)
        if not ok or not name.strip():
            return
        variant.name = name.strip()
        current = self.variant_list.currentItem()
        if current:
            current.setText(variant.name)

    def delete_variant(self) -> None:
        category = self.selected_category()
        variant = self.selected_variant()
        if not category or not variant:
            return
        category.variants = [item for item in category.variants if item.id != variant.id]
        self.current_variant_id = ""
        self.load_category()

    def accept(self) -> None:
        self.update_current_category()
        if not self.categories:
            QMessageBox.warning(self, "Sin categorias", "Debe existir al menos una categoria.")
            return
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_runtime_dirs()
        self.project, self.project_dir = self._load_initial_project()
        self.current_chapter_id = ""
        self.current_note_id = ""
        self.current_entity_id = ""
        self.field_widgets: dict[str, QWidget] = {}
        self._loading_chapter = False
        self._loading_note = False
        self._loading_entity = False
        self._loading_library = False
        self._loading_layout = False
        self._refreshing_dashboard = False
        self._dirty = False

        self.setWindowTitle("Pescritura")
        self.resize(1340, 820)
        self.setMinimumSize(1040, 680)
        self.setWindowOpacity(0.98)

        self.live_refresh_timer = QTimer(self)
        self.live_refresh_timer.setSingleShot(True)
        self.live_refresh_timer.setInterval(650)
        self.live_refresh_timer.timeout.connect(self.refresh_live_panels)

        self._build_actions()
        self._build_ui()
        self.reload_all()

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(15000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()

    def _load_initial_project(self) -> tuple[Project, Path]:
        projects = list_projects()
        if projects:
            try:
                return load_project(projects[0])
            except Exception:
                pass
        return create_project("Nueva obra")

    def _build_actions(self) -> None:
        toolbar = QToolBar("Archivo")
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize())
        self.addToolBar(toolbar)

        self.new_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon), "Nuevo", self)
        self.open_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon), "Abrir", self)
        self.import_csv_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Importar CSV", self)
        self.save_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Guardar", self)
        self.export_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton), "Exportar PDF", self)
        self.export_csv_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton), "Exportar CSV", self)
        self.backup_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon), "Respaldo", self)

        self.new_action.triggered.connect(self.new_project)
        self.open_action.triggered.connect(self.open_project)
        self.import_csv_action.triggered.connect(self.import_csv_project)
        self.save_action.triggered.connect(lambda: self.save_now(show_message=True))
        self.export_action.triggered.connect(self.export_pdf)
        self.export_csv_action.triggered.connect(self.export_csv)
        self.backup_action.triggered.connect(self.create_backup)

        for action in (
            self.new_action,
            self.open_action,
            self.import_csv_action,
            self.save_action,
            self.backup_action,
            self.export_action,
            self.export_csv_action,
        ):
            toolbar.addAction(action)

        file_menu = self.menuBar().addMenu("Archivo")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.import_csv_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.backup_action)
        file_menu.addAction(self.export_action)
        file_menu.addAction(self.export_csv_action)
        file_menu.addSeparator()
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _build_ui(self) -> None:
        central = BackdropWidget()
        central.setObjectName("Backdrop")
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = panel("HeaderPanel")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        title_box = QVBoxLayout()
        self.header_title = QLabel("Pescritura")
        self.header_title.setObjectName("AppTitle")
        self.header_meta = QLabel("")
        self.header_meta.setObjectName("MutedLabel")
        title_box.addWidget(self.header_title)
        title_box.addWidget(self.header_meta)
        header_layout.addLayout(title_box, 1)
        self.header_words = QLabel("0 palabras")
        self.header_words.setObjectName("Chip")
        self.header_save_state = QLabel("Guardado")
        self.header_save_state.setObjectName("Chip")
        header_layout.addWidget(self.header_words)
        header_layout.addWidget(self.header_save_state)
        root.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_library_tab(), "Biblioteca")
        self.tabs.addTab(self._build_dashboard_tab(), "Tablero")
        self.tabs.addTab(self._build_writing_tab(), "Escritura")
        self.tabs.addTab(self._build_notes_tab(), "Notas")
        self.tabs.addTab(self._build_world_tab(), "Mundo")
        self.tabs.addTab(self._build_layout_tab(), "Maquetacion")
        root.addWidget(self.tabs)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Listo")

    def _build_library_tab(self) -> QWidget:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left = panel()
        left_layout = QVBoxLayout(left)
        title = QLabel("Biblioteca de novelas")
        title.setObjectName("SectionTitle")
        left_layout.addWidget(title)
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Filtrar por titulo o autor...")
        left_layout.addWidget(self.library_search)
        self.project_library = QTreeWidget()
        self.project_library.setHeaderLabels(["Obra", "Autor", "Capitulos", "Palabras", "Actualizada"])
        self.project_library.setRootIsDecorated(False)
        self.project_library.setAlternatingRowColors(True)
        self.project_library.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.project_library, 1)

        library_buttons = QHBoxLayout()
        new_project = small_button("Nueva novela")
        open_project = small_button("Abrir")
        refresh = small_button("Actualizar")
        library_buttons.addWidget(new_project)
        library_buttons.addWidget(open_project)
        library_buttons.addWidget(refresh)
        left_layout.addLayout(library_buttons)
        splitter.addWidget(left)

        right = panel()
        right_layout = QVBoxLayout(right)
        detail_title = QLabel("Detalle")
        detail_title.setObjectName("SectionTitle")
        right_layout.addWidget(detail_title)
        self.library_title = QLabel("Sin seleccion")
        self.library_title.setObjectName("AppTitle")
        self.library_meta = QLabel("")
        self.library_meta.setObjectName("MutedLabel")
        self.library_path = QLabel("")
        self.library_path.setObjectName("MutedLabel")
        self.library_path.setWordWrap(True)
        right_layout.addWidget(self.library_title)
        right_layout.addWidget(self.library_meta)
        right_layout.addWidget(self.library_path)

        detail_stats = QGridLayout()
        self.library_words = StatCard("Palabras")
        self.library_chapters = StatCard("Capitulos")
        self.library_notes = StatCard("Notas")
        self.library_world = StatCard("Mundo")
        detail_stats.addWidget(self.library_words, 0, 0)
        detail_stats.addWidget(self.library_chapters, 0, 1)
        detail_stats.addWidget(self.library_notes, 1, 0)
        detail_stats.addWidget(self.library_world, 1, 1)
        right_layout.addLayout(detail_stats)

        self.library_synopsis = QTextBrowser()
        self.library_synopsis.setObjectName("LibrarySynopsis")
        self.library_synopsis.setMinimumHeight(220)
        right_layout.addWidget(self.library_synopsis, 1)
        right_actions = QHBoxLayout()
        open_selected = small_button("Abrir seleccionada")
        new_from_detail = small_button("Crear otra")
        right_actions.addStretch()
        right_actions.addWidget(new_from_detail)
        right_actions.addWidget(open_selected)
        right_layout.addLayout(right_actions)
        splitter.addWidget(right)
        splitter.setSizes([820, 420])

        self.library_search.textChanged.connect(self.refresh_project_library)
        self.project_library.currentItemChanged.connect(self.on_library_project_selected)
        self.project_library.itemDoubleClicked.connect(lambda _item, _column: self.open_selected_project())
        new_project.clicked.connect(self.new_project)
        new_from_detail.clicked.connect(self.new_project)
        open_project.clicked.connect(self.open_selected_project)
        open_selected.clicked.connect(self.open_selected_project)
        refresh.clicked.connect(self.refresh_project_library)
        return root

    def _build_dashboard_tab(self) -> QWidget:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left = panel()
        left_layout = QVBoxLayout(left)
        title = QLabel("Estado de la obra")
        title.setObjectName("SectionTitle")
        left_layout.addWidget(title)
        stats_grid = QGridLayout()
        self.stat_words = StatCard("Palabras")
        self.stat_chapters = StatCard("Capitulos")
        self.stat_notes = StatCard("Notas")
        self.stat_world = StatCard("Mundo")
        self.stat_assets = StatCard("Imagenes")
        stats_grid.addWidget(self.stat_words, 0, 0)
        stats_grid.addWidget(self.stat_chapters, 0, 1)
        stats_grid.addWidget(self.stat_notes, 1, 0)
        stats_grid.addWidget(self.stat_world, 1, 1)
        stats_grid.addWidget(self.stat_assets, 2, 0, 1, 2)
        left_layout.addLayout(stats_grid)
        progress_box = QGroupBox("Progreso general")
        progress_layout = QVBoxLayout(progress_box)
        self.project_progress = QProgressBar()
        self.project_progress_label = QLabel("")
        self.project_progress_label.setObjectName("MutedLabel")
        progress_layout.addWidget(self.project_progress)
        progress_layout.addWidget(self.project_progress_label)
        left_layout.addWidget(progress_box)
        left_layout.addWidget(QLabel("Mapa de capitulos"))
        self.chapter_map = QTreeWidget()
        self.chapter_map.setHeaderLabels(["Capitulo", "Estado", "Palabras", "Objetivo", "POV"])
        self.chapter_map.itemDoubleClicked.connect(self.open_chapter_from_map)
        left_layout.addWidget(self.chapter_map, 1)
        splitter.addWidget(left)

        right = panel()
        right_layout = QVBoxLayout(right)
        search_title = QLabel("Busqueda global")
        search_title.setObjectName("SectionTitle")
        right_layout.addWidget(search_title)
        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("Buscar en capitulos, notas, resumenes, fichas y campos...")
        right_layout.addWidget(self.global_search)
        self.search_results = QTreeWidget()
        self.search_results.setHeaderLabels(["Tipo", "Nombre", "Coincidencia"])
        self.search_results.itemDoubleClicked.connect(self.open_search_result)
        right_layout.addWidget(self.search_results, 2)
        right_layout.addWidget(QLabel("Categorias del mundo"))
        self.category_stats = QTreeWidget()
        self.category_stats.setHeaderLabels(["Categoria", "Entradas", "Campos", "Variantes"])
        right_layout.addWidget(self.category_stats, 1)
        splitter.addWidget(right)
        splitter.setSizes([720, 520])
        self.global_search.textChanged.connect(self.perform_global_search)
        return root

    def _build_writing_tab(self) -> QWidget:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left = panel()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Capitulos"))
        self.chapter_search = QLineEdit()
        self.chapter_search.setPlaceholderText("Filtrar capitulos...")
        left_layout.addWidget(self.chapter_search)
        self.chapter_list = QListWidget()
        left_layout.addWidget(self.chapter_list, 1)
        chapter_buttons = QGridLayout()
        add_chapter = small_button("+")
        delete_chapter = small_button("Eliminar")
        move_up = small_button("Subir")
        move_down = small_button("Bajar")
        duplicate_chapter = small_button("Duplicar")
        chapter_buttons.addWidget(add_chapter, 0, 0)
        chapter_buttons.addWidget(delete_chapter, 0, 1)
        chapter_buttons.addWidget(move_up, 1, 0)
        chapter_buttons.addWidget(move_down, 1, 1)
        chapter_buttons.addWidget(duplicate_chapter, 2, 0, 1, 2)
        left_layout.addLayout(chapter_buttons)
        splitter.addWidget(left)

        editor = panel()
        editor_layout = QVBoxLayout(editor)
        self.chapter_title = QLineEdit()
        self.chapter_title.setPlaceholderText("Titulo del capitulo")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.chapter_title.setFont(title_font)
        self.chapter_body = QTextEdit()
        self.chapter_body.setAcceptRichText(False)
        self.chapter_body.setPlaceholderText("Escribe la escena, capitulo o fragmento aqui...")
        text_actions = QHBoxLayout()
        scene_break = small_button("Corte de escena")
        text_actions.addStretch()
        text_actions.addWidget(scene_break)
        editor_layout.addWidget(self.chapter_title)
        editor_layout.addLayout(text_actions)
        editor_layout.addWidget(self.chapter_body, 1)
        splitter.addWidget(editor)

        right = panel()
        right_layout = QVBoxLayout(right)
        meta_box = QGroupBox("Metadatos")
        meta_form = QFormLayout(meta_box)
        self.chapter_status = QComboBox()
        self.chapter_status.addItems(CHAPTER_STATUSES)
        self.chapter_pov = QLineEdit()
        self.chapter_pov.setPlaceholderText("Personaje / narrador")
        self.chapter_target = QSpinBox()
        self.chapter_target.setRange(100, 50000)
        self.chapter_target.setSingleStep(250)
        self.chapter_summary = QTextEdit()
        self.chapter_summary.setAcceptRichText(False)
        self.chapter_summary.setMaximumHeight(92)
        self.chapter_progress = QProgressBar()
        self.chapter_progress_label = QLabel("")
        self.chapter_progress_label.setObjectName("MutedLabel")
        meta_form.addRow("Estado", self.chapter_status)
        meta_form.addRow("POV", self.chapter_pov)
        meta_form.addRow("Objetivo", self.chapter_target)
        meta_form.addRow("Resumen", self.chapter_summary)
        meta_form.addRow("Progreso", self.chapter_progress)
        meta_form.addRow("", self.chapter_progress_label)
        right_layout.addWidget(meta_box)
        right_layout.addWidget(QLabel("Notas del capitulo"))
        self.chapter_notes = QTextEdit()
        self.chapter_notes.setAcceptRichText(False)
        self.chapter_notes.setMaximumHeight(150)
        right_layout.addWidget(self.chapter_notes)
        right_layout.addWidget(QLabel("Imagenes asignadas"))
        self.chapter_images = QListWidget()
        self.configure_image_list(self.chapter_images)
        right_layout.addWidget(self.chapter_images, 1)
        image_buttons = QHBoxLayout()
        add_image = small_button("Imagen +")
        remove_image = small_button("Quitar")
        preview_image = small_button("Ver")
        image_buttons.addWidget(add_image)
        image_buttons.addWidget(remove_image)
        image_buttons.addWidget(preview_image)
        right_layout.addLayout(image_buttons)
        word_box = QGroupBox("Conteo")
        word_layout = QFormLayout(word_box)
        self.word_count_label = QLabel("0")
        self.char_count_label = QLabel("0")
        word_layout.addRow("Palabras", self.word_count_label)
        word_layout.addRow("Caracteres", self.char_count_label)
        right_layout.addWidget(word_box)
        splitter.addWidget(right)
        splitter.setSizes([240, 760, 260])

        self.chapter_list.currentItemChanged.connect(self.on_chapter_selected)
        self.chapter_search.textChanged.connect(self.refresh_chapters)
        add_chapter.clicked.connect(self.add_chapter)
        delete_chapter.clicked.connect(self.delete_chapter)
        move_up.clicked.connect(lambda: self.move_chapter(-1))
        move_down.clicked.connect(lambda: self.move_chapter(1))
        duplicate_chapter.clicked.connect(self.duplicate_chapter)
        scene_break.clicked.connect(self.insert_scene_break)
        add_image.clicked.connect(self.add_chapter_images)
        remove_image.clicked.connect(self.remove_chapter_image)
        preview_image.clicked.connect(lambda: self.preview_selected_asset(self.chapter_images))
        self.chapter_images.itemDoubleClicked.connect(lambda _item: self.preview_selected_asset(self.chapter_images))
        self.chapter_title.textChanged.connect(self.mark_dirty)
        self.chapter_body.textChanged.connect(self.on_body_changed)
        self.chapter_notes.textChanged.connect(self.mark_dirty)
        self.chapter_summary.textChanged.connect(self.mark_dirty)
        self.chapter_status.currentIndexChanged.connect(self.mark_dirty)
        self.chapter_pov.textChanged.connect(self.mark_dirty)
        self.chapter_target.valueChanged.connect(self.mark_dirty)
        self.chapter_target.valueChanged.connect(self.update_counts)
        return root

    def _build_notes_tab(self) -> QWidget:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left = panel()
        left_layout = QVBoxLayout(left)
        title = QLabel("Notas de obra")
        title.setObjectName("SectionTitle")
        left_layout.addWidget(title)
        self.note_category_filter = QComboBox()
        left_layout.addWidget(self.note_category_filter)
        self.note_search = QLineEdit()
        self.note_search.setPlaceholderText("Filtrar notas...")
        left_layout.addWidget(self.note_search)
        self.note_list = QListWidget()
        left_layout.addWidget(self.note_list, 1)
        note_buttons = QGridLayout()
        add_note = small_button("Nota +")
        delete_note = small_button("Eliminar")
        duplicate_note = small_button("Duplicar")
        note_buttons.addWidget(add_note, 0, 0)
        note_buttons.addWidget(delete_note, 0, 1)
        note_buttons.addWidget(duplicate_note, 1, 0, 1, 2)
        left_layout.addLayout(note_buttons)
        splitter.addWidget(left)

        editor = panel()
        editor_layout = QVBoxLayout(editor)
        self.note_title = QLineEdit()
        self.note_title.setPlaceholderText("Titulo de la nota")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.note_title.setFont(title_font)
        note_meta = QHBoxLayout()
        self.note_category = QComboBox()
        self.note_category.setEditable(True)
        self.note_category.setMinimumWidth(220)
        self.note_pin = QCheckBox("Fijar")
        self.note_updated = QLabel("")
        self.note_updated.setObjectName("MutedLabel")
        note_meta.addWidget(QLabel("Categoria"))
        note_meta.addWidget(self.note_category, 1)
        note_meta.addWidget(self.note_pin)
        note_meta.addStretch()
        note_meta.addWidget(self.note_updated)
        self.note_body = QTextEdit()
        self.note_body.setAcceptRichText(False)
        self.note_body.setPlaceholderText("Ideas, investigacion, pendientes o cualquier material que no forma parte de la novela...")
        editor_layout.addWidget(self.note_title)
        editor_layout.addLayout(note_meta)
        editor_layout.addWidget(self.note_body, 1)
        splitter.addWidget(editor)

        side = panel()
        side_layout = QVBoxLayout(side)
        side_title = QLabel("Resumen")
        side_title.setObjectName("SectionTitle")
        side_layout.addWidget(side_title)
        self.note_words = StatCard("Palabras")
        self.note_chars = StatCard("Caracteres")
        self.note_total = StatCard("Notas")
        side_layout.addWidget(self.note_words)
        side_layout.addWidget(self.note_chars)
        side_layout.addWidget(self.note_total)
        side_layout.addStretch()
        splitter.addWidget(side)
        splitter.setSizes([260, 760, 260])

        self.note_category_filter.currentIndexChanged.connect(self.refresh_notes)
        self.note_search.textChanged.connect(self.refresh_notes)
        self.note_list.currentItemChanged.connect(self.on_note_selected)
        add_note.clicked.connect(self.add_note)
        delete_note.clicked.connect(self.delete_note)
        duplicate_note.clicked.connect(self.duplicate_note)
        self.note_title.textChanged.connect(self.mark_dirty)
        self.note_body.textChanged.connect(self.on_note_body_changed)
        self.note_category.currentTextChanged.connect(self.mark_dirty)
        self.note_pin.toggled.connect(self.mark_dirty)
        return root

    def _build_world_tab(self) -> QWidget:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left = panel()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Categoria"))
        self.entity_category_filter = QComboBox()
        left_layout.addWidget(self.entity_category_filter)
        self.entity_search = QLineEdit()
        self.entity_search.setPlaceholderText("Filtrar fichas...")
        left_layout.addWidget(self.entity_search)
        self.entity_list = QListWidget()
        left_layout.addWidget(self.entity_list, 1)
        entity_buttons = QGridLayout()
        add_entity = small_button("Entrada +")
        delete_entity = small_button("Eliminar")
        duplicate_entity = small_button("Duplicar")
        schema_button = small_button("Campos")
        entity_buttons.addWidget(add_entity, 0, 0)
        entity_buttons.addWidget(delete_entity, 0, 1)
        entity_buttons.addWidget(duplicate_entity, 1, 0, 1, 2)
        entity_buttons.addWidget(schema_button, 2, 0, 1, 2)
        left_layout.addLayout(entity_buttons)
        splitter.addWidget(left)

        editor = panel()
        editor_layout = QVBoxLayout(editor)
        form = QFormLayout()
        self.entity_name = QLineEdit()
        self.entity_category_combo = QComboBox()
        self.entity_variant_combo = QComboBox()
        self.entity_summary = QTextEdit()
        self.entity_summary.setAcceptRichText(False)
        self.entity_summary.setMaximumHeight(120)
        form.addRow("Nombre", self.entity_name)
        form.addRow("Categoria", self.entity_category_combo)
        form.addRow("Variante", self.entity_variant_combo)
        form.addRow("Resumen", self.entity_summary)
        editor_layout.addLayout(form)

        self.dynamic_fields_container = QWidget()
        self.dynamic_fields_layout = QFormLayout(self.dynamic_fields_container)
        self.dynamic_fields_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        fields_scroll = QScrollArea()
        fields_scroll.setWidgetResizable(True)
        fields_scroll.setWidget(self.dynamic_fields_container)
        editor_layout.addWidget(fields_scroll, 1)
        splitter.addWidget(editor)

        photos = panel()
        photos_layout = QVBoxLayout(photos)
        photos_layout.addWidget(QLabel("Fotos / referencias"))
        self.entity_photos = QListWidget()
        self.configure_image_list(self.entity_photos)
        photos_layout.addWidget(self.entity_photos, 1)
        photo_buttons = QHBoxLayout()
        add_photo = small_button("Foto +")
        remove_photo = small_button("Quitar")
        preview_photo = small_button("Ver")
        photo_buttons.addWidget(add_photo)
        photo_buttons.addWidget(remove_photo)
        photo_buttons.addWidget(preview_photo)
        photos_layout.addLayout(photo_buttons)
        splitter.addWidget(photos)
        splitter.setSizes([260, 760, 260])

        self.entity_category_filter.currentIndexChanged.connect(self.refresh_entities)
        self.entity_search.textChanged.connect(self.refresh_entities)
        self.entity_list.currentItemChanged.connect(self.on_entity_selected)
        add_entity.clicked.connect(self.add_entity)
        delete_entity.clicked.connect(self.delete_entity)
        duplicate_entity.clicked.connect(self.duplicate_entity)
        schema_button.clicked.connect(self.edit_schema)
        add_photo.clicked.connect(self.add_entity_photos)
        remove_photo.clicked.connect(self.remove_entity_photo)
        preview_photo.clicked.connect(lambda: self.preview_selected_asset(self.entity_photos))
        self.entity_photos.itemDoubleClicked.connect(lambda _item: self.preview_selected_asset(self.entity_photos))
        self.entity_name.textChanged.connect(self.mark_dirty)
        self.entity_summary.textChanged.connect(self.mark_dirty)
        self.entity_category_combo.currentIndexChanged.connect(self.on_entity_category_changed)
        self.entity_variant_combo.currentIndexChanged.connect(self.on_entity_variant_changed)
        return root

    def _build_layout_tab(self) -> QWidget:
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        left = panel()
        left_layout = QVBoxLayout(left)

        project_box = QGroupBox("Obra")
        project_form = QFormLayout(project_box)
        self.project_title = QLineEdit()
        self.project_author = QLineEdit()
        self.project_target = QSpinBox()
        self.project_target.setRange(1000, 1000000)
        self.project_target.setSingleStep(5000)
        self.project_synopsis = QTextEdit()
        self.project_synopsis.setAcceptRichText(False)
        self.project_synopsis.setMinimumHeight(130)
        project_form.addRow("Titulo", self.project_title)
        project_form.addRow("Autor", self.project_author)
        project_form.addRow("Objetivo palabras", self.project_target)
        project_form.addRow("Sinopsis", self.project_synopsis)
        left_layout.addWidget(project_box)

        page_box = QGroupBox("Pagina")
        page_form = QFormLayout(page_box)
        self.page_size = QComboBox()
        self.page_size.addItems(["A4", "Carta"])
        self.margin_top = self._mm_spin()
        self.margin_right = self._mm_spin()
        self.margin_bottom = self._mm_spin()
        self.margin_left = self._mm_spin()
        page_form.addRow("Tamano", self.page_size)
        page_form.addRow("Margen superior mm", self.margin_top)
        page_form.addRow("Margen derecho mm", self.margin_right)
        page_form.addRow("Margen inferior mm", self.margin_bottom)
        page_form.addRow("Margen izquierdo mm", self.margin_left)
        left_layout.addWidget(page_box)

        cover_box = QGroupBox("Portada visual")
        cover_layout = QVBoxLayout(cover_box)
        self.cover_label = QLabel("Sin imagen de portada")
        self.cover_label.setObjectName("MutedLabel")
        self.cover_preview = QLabel()
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setMinimumHeight(130)
        self.cover_preview.setObjectName("GlassPanel")
        cover_buttons = QHBoxLayout()
        set_cover = small_button("Asignar")
        clear_cover = small_button("Quitar")
        preview_cover = small_button("Ver")
        cover_buttons.addWidget(set_cover)
        cover_buttons.addWidget(clear_cover)
        cover_buttons.addWidget(preview_cover)
        cover_layout.addWidget(self.cover_label)
        cover_layout.addWidget(self.cover_preview)
        cover_layout.addLayout(cover_buttons)
        left_layout.addWidget(cover_box)
        outer.addWidget(left, 1)

        right = panel()
        right_layout = QVBoxLayout(right)
        text_box = QGroupBox("Texto y estructura")
        text_form = QFormLayout(text_box)
        self.font_family = QFontComboBox()
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 24)
        self.line_height = QDoubleSpinBox()
        self.line_height.setRange(1.0, 2.4)
        self.line_height.setSingleStep(0.05)
        self.line_height.setDecimals(2)
        self.paragraph_spacing = QSpinBox()
        self.paragraph_spacing.setRange(0, 32)
        self.align_combo = QComboBox()
        self.align_combo.addItem("Justificado", "justify")
        self.align_combo.addItem("Izquierda", "left")
        self.align_combo.addItem("Centro", "center")
        self.align_combo.addItem("Derecha", "right")
        self.title_page_check = QCheckBox("Portada")
        self.toc_check = QCheckBox("Indice")
        self.world_appendix_check = QCheckBox("Apéndice de mundo")
        self.chapter_page_check = QCheckBox("Cada capitulo inicia pagina")
        self.page_numbers_check = QCheckBox("Numeracion")
        self.header_check = QCheckBox("Encabezado")
        self.chapter_images_check = QCheckBox("Exportar imagenes de capitulos")
        self.entity_photos_check = QCheckBox("Exportar fotos del mundo")
        text_form.addRow("Fuente", self.font_family)
        text_form.addRow("Tamano pt", self.font_size)
        text_form.addRow("Interlineado", self.line_height)
        text_form.addRow("Espacio parrafo pt", self.paragraph_spacing)
        text_form.addRow("Alineacion", self.align_combo)
        text_form.addRow("", self.title_page_check)
        text_form.addRow("", self.toc_check)
        text_form.addRow("", self.world_appendix_check)
        text_form.addRow("", self.chapter_page_check)
        text_form.addRow("", self.page_numbers_check)
        text_form.addRow("", self.header_check)
        text_form.addRow("", self.chapter_images_check)
        text_form.addRow("", self.entity_photos_check)
        right_layout.addWidget(text_box)

        preview_box = QGroupBox("Vista previa del PDF")
        preview_layout = QVBoxLayout(preview_box)
        self.pdf_preview = QTextBrowser()
        self.pdf_preview.setObjectName("PdfPreview")
        self.pdf_preview.setOpenExternalLinks(False)
        self.pdf_preview.setMinimumHeight(300)
        refresh_preview = small_button("Actualizar vista")
        preview_layout.addWidget(self.pdf_preview, 1)
        preview_layout.addWidget(refresh_preview)
        right_layout.addWidget(preview_box, 1)

        actions = QHBoxLayout()
        save = small_button("Guardar")
        export = small_button("Exportar PDF")
        actions.addStretch()
        actions.addWidget(save)
        actions.addWidget(export)
        right_layout.addLayout(actions)
        right_layout.addStretch()
        outer.addWidget(right, 1)

        save.clicked.connect(lambda: self.save_now(show_message=True))
        export.clicked.connect(self.export_pdf)
        set_cover.clicked.connect(self.set_cover_image)
        clear_cover.clicked.connect(self.clear_cover_image)
        preview_cover.clicked.connect(self.preview_cover_image)
        refresh_preview.clicked.connect(self.update_pdf_preview)
        self.project_title.textChanged.connect(self.mark_dirty)
        self.project_author.textChanged.connect(self.mark_dirty)
        self.project_target.valueChanged.connect(self.mark_dirty)
        self.project_synopsis.textChanged.connect(self.mark_dirty)
        for widget in (
            self.page_size,
            self.margin_top,
            self.margin_right,
            self.margin_bottom,
            self.margin_left,
            self.font_family,
            self.font_size,
            self.line_height,
            self.paragraph_spacing,
            self.align_combo,
            self.title_page_check,
            self.toc_check,
            self.world_appendix_check,
            self.chapter_page_check,
            self.page_numbers_check,
            self.header_check,
            self.chapter_images_check,
            self.entity_photos_check,
        ):
            if isinstance(widget, (QComboBox, QFontComboBox)):
                widget.currentIndexChanged.connect(self.mark_dirty)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self.mark_dirty)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self.mark_dirty)
        return root

    def _mm_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(5.0, 80.0)
        spin.setDecimals(1)
        spin.setSingleStep(1.0)
        return spin

    def reload_all(self) -> None:
        self._loading_layout = True
        self.project_title.setText(self.project.title)
        self.project_author.setText(self.project.author)
        self.project_target.setValue(int(self.project.target_words))
        self.project_synopsis.setPlainText(self.project.synopsis)
        self.load_layout_settings()
        self._loading_layout = False
        self.refresh_project_library()
        self.refresh_chapters()
        self.refresh_note_categories()
        self.refresh_notes()
        self.refresh_category_controls()
        self.refresh_entities()
        self.refresh_live_panels()
        self._dirty = False
        self.statusBar().showMessage(f"Obra abierta: {self.project.title}")

    def load_layout_settings(self) -> None:
        layout = self.project.layout
        self.page_size.setCurrentText(layout.page_size)
        self.margin_top.setValue(float(layout.margin_top_mm))
        self.margin_right.setValue(float(layout.margin_right_mm))
        self.margin_bottom.setValue(float(layout.margin_bottom_mm))
        self.margin_left.setValue(float(layout.margin_left_mm))
        self.font_family.setCurrentFont(QFont(layout.font_family))
        self.font_size.setValue(int(layout.font_size_pt))
        self.line_height.setValue(float(layout.line_height))
        self.paragraph_spacing.setValue(int(layout.paragraph_spacing_pt))
        index = self.align_combo.findData(layout.align)
        self.align_combo.setCurrentIndex(index if index >= 0 else 0)
        self.title_page_check.setChecked(layout.include_title_page)
        self.toc_check.setChecked(layout.include_toc)
        self.world_appendix_check.setChecked(layout.include_world_appendix)
        self.chapter_page_check.setChecked(layout.chapter_starts_new_page)
        self.page_numbers_check.setChecked(layout.show_page_numbers)
        self.header_check.setChecked(layout.show_header)
        self.chapter_images_check.setChecked(layout.include_chapter_images)
        self.entity_photos_check.setChecked(layout.include_entity_photos)
        self.update_cover_preview()

    def sync_project_from_ui(self) -> None:
        self.project.title = self.project_title.text().strip() or "Nueva obra"
        self.project.author = self.project_author.text().strip()
        self.project.synopsis = self.project_synopsis.toPlainText().strip()
        self.project.target_words = int(self.project_target.value())
        cover_image = self.project.layout.cover_image
        self.project.layout = LayoutSettings(
            page_size=self.page_size.currentText(),
            margin_top_mm=float(self.margin_top.value()),
            margin_right_mm=float(self.margin_right.value()),
            margin_bottom_mm=float(self.margin_bottom.value()),
            margin_left_mm=float(self.margin_left.value()),
            font_family=self.font_family.currentFont().family(),
            font_size_pt=int(self.font_size.value()),
            line_height=float(self.line_height.value()),
            paragraph_spacing_pt=int(self.paragraph_spacing.value()),
            align=self.align_combo.currentData(),
            include_title_page=self.title_page_check.isChecked(),
            include_toc=self.toc_check.isChecked(),
            include_world_appendix=self.world_appendix_check.isChecked(),
            chapter_starts_new_page=self.chapter_page_check.isChecked(),
            show_page_numbers=self.page_numbers_check.isChecked(),
            show_header=self.header_check.isChecked(),
            cover_image=cover_image,
            include_chapter_images=self.chapter_images_check.isChecked(),
            include_entity_photos=self.entity_photos_check.isChecked(),
        )

    def mark_dirty(self, *_args: Any) -> None:
        if self._loading_chapter or self._loading_note or self._loading_entity or self._loading_layout:
            return
        self._dirty = True
        if hasattr(self, "header_save_state"):
            self.header_save_state.setText("Cambios sin guardar")
        if hasattr(self, "live_refresh_timer"):
            self.live_refresh_timer.start()

    def autosave(self) -> None:
        if self._dirty:
            self.save_now(show_message=False)

    def save_now(self, show_message: bool = False) -> None:
        self.save_current_chapter()
        self.save_current_note()
        self.save_current_entity()
        self.sync_project_from_ui()
        save_project(self.project, self.project_dir)
        self._dirty = False
        self.header_save_state.setText("Guardado")
        self.refresh_project_library()
        self.refresh_live_panels()
        message = f"Guardado: {self.project.title}"
        self.statusBar().showMessage(message, 5000)
        if show_message:
            QMessageBox.information(self, "Guardado", message)

    def new_project(self, *_args: Any) -> None:
        self.save_now(show_message=False)
        title, ok = QInputDialog.getText(self, "Nueva obra", "Titulo")
        if not ok:
            return
        title = title.strip() or "Nueva obra"
        author, ok_author = QInputDialog.getText(self, "Autor", "Autor")
        author = author.strip() if ok_author else ""
        self.project, self.project_dir = create_project(title, author)
        self.current_chapter_id = ""
        self.current_note_id = ""
        self.current_entity_id = ""
        self.reload_all()

    def open_project(self, *_args: Any) -> None:
        self.save_now(show_message=False)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir obra",
            str(self.project_dir.parent),
            "Proyecto Pescritura (project.json);;JSON (*.json)",
        )
        if not path:
            return
        try:
            self.project, self.project_dir = load_project(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        self.current_chapter_id = ""
        self.current_note_id = ""
        self.current_entity_id = ""
        self.reload_all()

    def import_csv_project(self, *_args: Any) -> None:
        self.save_now(show_message=False)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar CSV",
            str(self.project_dir.parent),
            "CSV (*.csv)",
        )
        if not path:
            return
        try:
            self.project, self.project_dir = create_project_from_csv(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo importar", str(exc))
            return
        self.current_chapter_id = ""
        self.current_note_id = ""
        self.current_entity_id = ""
        self.reload_all()

    def export_pdf(self, *_args: Any) -> None:
        self.save_now(show_message=False)
        suggested = default_pdf_path(self.project)
        path, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", str(suggested), "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            export_project_pdf(self.project, self.project_dir, Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Exportacion fallida", str(exc))
            return
        self.statusBar().showMessage(f"PDF exportado: {path}", 7000)
        QMessageBox.information(self, "PDF exportado", f"Se exporto el PDF:\n{path}")

    def export_csv(self, *_args: Any) -> None:
        self.save_now(show_message=False)
        suggested = default_csv_path(self.project)
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", str(suggested), "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            export_project_csv(self.project, self.project_dir, Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Exportacion fallida", str(exc))
            return
        self.statusBar().showMessage(f"CSV exportado: {path}", 7000)
        QMessageBox.information(self, "CSV exportado", f"Se exporto el CSV:\n{path}")

    def create_backup(self, *_args: Any) -> None:
        try:
            self.save_now(show_message=False)
            backup_path = create_project_backup(self.project_dir)
        except Exception as exc:
            QMessageBox.critical(self, "Respaldo fallido", str(exc))
            return
        self.statusBar().showMessage(f"Respaldo creado: {backup_path}", 7000)
        QMessageBox.information(self, "Respaldo creado", f"Se creo el respaldo:\n{backup_path}")

    def refresh_project_library(self, *_args: Any) -> None:
        if not hasattr(self, "project_library") or self._loading_library:
            return
        query = self.library_search.text().strip().lower() if hasattr(self, "library_search") else ""
        current_dir = self.project_dir.resolve() if hasattr(self, "project_dir") else None
        selected_item: QTreeWidgetItem | None = None
        self._loading_library = True
        self.project_library.clear()
        for project_file in list_projects():
            try:
                project, project_dir = load_project(project_file)
            except Exception:
                continue
            haystack = " ".join([project.title, project.author, project.synopsis]).lower()
            if query and query not in haystack:
                continue
            words = sum(word_count(chapter.body) for chapter in project.chapters)
            title = project.title
            if current_dir and project_dir.resolve() == current_dir:
                title = f"{title} (abierta)"
            item = QTreeWidgetItem(
                [
                    title,
                    project.author,
                    str(len(project.chapters)),
                    str(words),
                    self.short_date(project.updated_at),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, str(project_file))
            self.project_library.addTopLevelItem(item)
            if current_dir and project_dir.resolve() == current_dir:
                selected_item = item
        self._loading_library = False
        for column in range(1, self.project_library.columnCount()):
            self.project_library.resizeColumnToContents(column)
        if selected_item:
            self.project_library.setCurrentItem(selected_item)
            self.update_library_detail(selected_item)
        elif self.project_library.topLevelItemCount():
            first = self.project_library.topLevelItem(0)
            self.project_library.setCurrentItem(first)
            self.update_library_detail(first)
        else:
            self.update_library_detail(None)

    def selected_library_project_path(self) -> Path | None:
        current = self.project_library.currentItem() if hasattr(self, "project_library") else None
        if not current:
            return None
        value = current.data(0, Qt.ItemDataRole.UserRole)
        return Path(value) if value else None

    def on_library_project_selected(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None = None) -> None:
        if self._loading_library:
            return
        self.update_library_detail(current)

    def update_library_detail(self, item: QTreeWidgetItem | None) -> None:
        if not hasattr(self, "library_title"):
            return
        if not item:
            self.library_title.setText("Sin novelas")
            self.library_meta.setText("")
            self.library_path.setText("")
            self.library_synopsis.clear()
            for card in (self.library_words, self.library_chapters, self.library_notes, self.library_world):
                card.set_values("0", "")
            return
        project_path = Path(item.data(0, Qt.ItemDataRole.UserRole))
        try:
            project, project_dir = load_project(project_path)
        except Exception as exc:
            self.library_title.setText("No se pudo leer")
            self.library_meta.setText(str(exc))
            self.library_path.setText(str(project_path))
            self.library_synopsis.clear()
            return
        words = sum(word_count(chapter.body) for chapter in project.chapters)
        self.library_title.setText(project.title)
        self.library_meta.setText(f"{project.author or 'Sin autor'} · Actualizada {self.short_date(project.updated_at)}")
        self.library_path.setText(str(project_dir))
        self.library_words.set_values(str(words), f"Objetivo: {project.target_words}")
        self.library_chapters.set_values(str(len(project.chapters)), self.chapter_status_summary(project))
        self.library_notes.set_values(str(len(project.notes)), self.note_category_summary(project))
        self.library_world.set_values(str(len(project.entities)), f"{len(project.categories)} categorias")
        self.library_synopsis.setPlainText(project.synopsis or "Sin sinopsis.")

    def open_selected_project(self, *_args: Any) -> None:
        path = self.selected_library_project_path()
        if not path:
            return
        if path.parent.resolve() == self.project_dir.resolve():
            self.tabs.setCurrentIndex(1)
            return
        self.save_now(show_message=False)
        try:
            self.project, self.project_dir = load_project(path)
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo abrir", str(exc))
            return
        self.current_chapter_id = ""
        self.current_note_id = ""
        self.current_entity_id = ""
        self.reload_all()
        self.tabs.setCurrentIndex(1)

    def short_date(self, value: str) -> str:
        if not value:
            return ""
        return value.replace("T", " ").split(".")[0][:16]

    def refresh_chapters(self, *_args: Any, save_current: bool = True) -> None:
        if save_current:
            self.save_current_chapter()
        query = self.chapter_search.text().strip().lower() if hasattr(self, "chapter_search") else ""
        self._loading_chapter = True
        self.chapter_list.clear()
        for chapter in self.project.chapters:
            haystack = " ".join([chapter.title, chapter.summary, chapter.notes, chapter.body, chapter.pov, chapter.status]).lower()
            if query and query not in haystack:
                continue
            words = word_count(chapter.body)
            item = QListWidgetItem(f"{chapter.title}\n{chapter.status} · {words} palabras")
            item.setData(Qt.ItemDataRole.UserRole, chapter.id)
            self.chapter_list.addItem(item)
        self._loading_chapter = False
        if self.chapter_list.count():
            row = 0
            if self.current_chapter_id:
                for index in range(self.chapter_list.count()):
                    if self.chapter_list.item(index).data(Qt.ItemDataRole.UserRole) == self.current_chapter_id:
                        row = index
                        break
            self.chapter_list.setCurrentRow(row)
            chapter = self.project.chapter_by_id(self.chapter_list.item(row).data(Qt.ItemDataRole.UserRole))
            if chapter:
                self.load_chapter(chapter)
        elif self.project.chapters:
            self.load_chapter(self.project.chapters[0])

    def on_chapter_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if self._loading_chapter:
            return
        if previous:
            self.save_current_chapter()
        chapter_id = current.data(Qt.ItemDataRole.UserRole) if current else ""
        chapter = self.project.chapter_by_id(chapter_id)
        if chapter:
            self.load_chapter(chapter)

    def load_chapter(self, chapter: Chapter) -> None:
        self._loading_chapter = True
        self.current_chapter_id = chapter.id
        self.chapter_title.setText(chapter.title)
        self.chapter_status.setCurrentText(chapter.status if chapter.status in CHAPTER_STATUSES else "Borrador")
        self.chapter_pov.setText(chapter.pov)
        self.chapter_target.setValue(int(chapter.target_words))
        self.chapter_summary.setPlainText(chapter.summary)
        self.chapter_body.setPlainText(chapter.body)
        self.chapter_notes.setPlainText(chapter.notes)
        self.refresh_chapter_images(chapter)
        self.update_counts()
        self._loading_chapter = False

    def save_current_chapter(self) -> None:
        if not self.current_chapter_id:
            return
        chapter = self.project.chapter_by_id(self.current_chapter_id)
        if not chapter:
            return
        chapter.title = self.chapter_title.text().strip() or "Capitulo sin titulo"
        chapter.status = self.chapter_status.currentText()
        chapter.pov = self.chapter_pov.text().strip()
        chapter.target_words = int(self.chapter_target.value())
        chapter.summary = self.chapter_summary.toPlainText().strip()
        chapter.body = self.chapter_body.toPlainText()
        chapter.notes = self.chapter_notes.toPlainText()
        current = self.chapter_list.currentItem()
        if current:
            current.setText(f"{chapter.title}\n{chapter.status} · {word_count(chapter.body)} palabras")

    def add_chapter(self) -> None:
        self.save_current_chapter()
        title, ok = QInputDialog.getText(self, "Nuevo capitulo", "Titulo")
        if not ok:
            return
        chapter = Chapter(id=new_id("chapter"), title=title.strip() or f"Capitulo {len(self.project.chapters) + 1}")
        self.project.chapters.append(chapter)
        self.current_chapter_id = chapter.id
        self.refresh_chapters(save_current=False)
        self.mark_dirty()

    def delete_chapter(self) -> None:
        if len(self.project.chapters) <= 1:
            QMessageBox.warning(self, "Capitulo requerido", "La obra necesita al menos un capitulo.")
            return
        current = self.chapter_list.currentItem()
        if not current:
            return
        chapter_id = current.data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(self, "Eliminar capitulo", "Eliminar este capitulo de la obra?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.project.chapters = [item for item in self.project.chapters if item.id != chapter_id]
        self.current_chapter_id = self.project.chapters[0].id
        self.refresh_chapters(save_current=False)
        self.mark_dirty()

    def move_chapter(self, direction: int) -> None:
        current = self.chapter_list.currentRow()
        target = current + direction
        if current < 0 or target < 0 or target >= len(self.project.chapters):
            return
        self.save_current_chapter()
        self.project.chapters[current], self.project.chapters[target] = self.project.chapters[target], self.project.chapters[current]
        self.current_chapter_id = self.project.chapters[target].id
        self.refresh_chapters(save_current=False)
        self.chapter_list.setCurrentRow(target)
        self.mark_dirty()

    def on_body_changed(self) -> None:
        self.update_counts()
        self.mark_dirty()

    def update_counts(self, *_args: Any) -> None:
        text = self.chapter_body.toPlainText()
        words = word_count(text)
        self.word_count_label.setText(str(words))
        self.char_count_label.setText(str(len(text)))
        target = self.chapter_target.value() if hasattr(self, "chapter_target") else 0
        if hasattr(self, "chapter_progress"):
            self.chapter_progress.setValue(percent(words, target))
            self.chapter_progress_label.setText(f"{words} de {target} palabras")

    def refresh_chapter_images(self, chapter: Chapter) -> None:
        self.chapter_images.clear()
        for image in chapter.images:
            item = self.asset_list_item(image)
            item.setData(Qt.ItemDataRole.UserRole, image)
            self.chapter_images.addItem(item)

    def add_chapter_images(self) -> None:
        chapter = self.project.chapter_by_id(self.current_chapter_id)
        if not chapter:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Asignar imagenes", str(Path.home()), IMAGE_FILTER)
        if not paths:
            return
        for item in paths:
            chapter.images.append(copy_asset(self.project_dir, Path(item), "chapters"))
        self.refresh_chapter_images(chapter)
        self.mark_dirty()

    def remove_chapter_image(self) -> None:
        chapter = self.project.chapter_by_id(self.current_chapter_id)
        current = self.chapter_images.currentItem()
        if not chapter or not current:
            return
        rel = current.data(Qt.ItemDataRole.UserRole)
        chapter.images = [item for item in chapter.images if item != rel]
        self.refresh_chapter_images(chapter)
        self.mark_dirty()

    def duplicate_chapter(self) -> None:
        self.save_current_chapter()
        chapter = self.project.chapter_by_id(self.current_chapter_id)
        if not chapter:
            return
        clone = copy.deepcopy(chapter)
        clone.id = new_id("chapter")
        clone.title = f"{chapter.title} copia"
        index = self.project.chapters.index(chapter) + 1
        self.project.chapters.insert(index, clone)
        self.current_chapter_id = clone.id
        self.refresh_chapters(save_current=False)
        self.mark_dirty()

    def insert_scene_break(self) -> None:
        cursor = self.chapter_body.textCursor()
        cursor.insertText("\n\n* * *\n\n")
        self.chapter_body.setTextCursor(cursor)
        self.chapter_body.setFocus()
        self.mark_dirty()

    def note_categories(self) -> list[str]:
        base = {"General", "Ideas", "Investigacion", "Pendientes"}
        base.update((note.category or "General").strip() or "General" for note in self.project.notes)
        return sorted(base, key=str.lower)

    def refresh_note_categories(self) -> None:
        if not hasattr(self, "note_category_filter"):
            return
        current_filter = self.note_category_filter.currentData()
        current_editor = self.note_category.currentText().strip() if hasattr(self, "note_category") else ""
        categories = self.note_categories()
        self._loading_note = True
        self.note_category_filter.clear()
        self.note_category_filter.addItem("Todas", "")
        for category in categories:
            self.note_category_filter.addItem(category, category)
        if current_filter:
            index = self.note_category_filter.findData(current_filter)
            self.note_category_filter.setCurrentIndex(index if index >= 0 else 0)
        self.note_category.clear()
        self.note_category.addItems(categories)
        if current_editor:
            index = self.note_category.findText(current_editor)
            if index < 0:
                self.note_category.addItem(current_editor)
                index = self.note_category.findText(current_editor)
            self.note_category.setCurrentIndex(index if index >= 0 else 0)
        self._loading_note = False

    def refresh_notes(self, *_args: Any, save_current: bool = True) -> None:
        if self._loading_note:
            return
        if save_current:
            self.save_current_note()
        category = self.note_category_filter.currentData() if hasattr(self, "note_category_filter") else ""
        query = self.note_search.text().strip().lower() if hasattr(self, "note_search") else ""
        self._loading_note = True
        self.note_list.clear()
        for note in sorted(self.project.notes, key=lambda item: (not item.pinned, item.category.lower(), item.title.lower())):
            if category and note.category != category:
                continue
            haystack = "\n".join([note.title, note.category, note.body]).lower()
            if query and query not in haystack:
                continue
            words = word_count(note.body)
            prefix = "[Fija] " if note.pinned else ""
            item = QListWidgetItem(f"{prefix}{note.title}\n{note.category} · {words} palabras")
            item.setData(Qt.ItemDataRole.UserRole, note.id)
            self.note_list.addItem(item)
        self._loading_note = False
        if self.note_list.count():
            row = 0
            if self.current_note_id:
                for index in range(self.note_list.count()):
                    if self.note_list.item(index).data(Qt.ItemDataRole.UserRole) == self.current_note_id:
                        row = index
                        break
            self.note_list.setCurrentRow(row)
            note = self.project.note_by_id(self.note_list.item(row).data(Qt.ItemDataRole.UserRole))
            if note:
                self.load_note(note)
        else:
            self.clear_note_editor()
        self.update_note_stats()

    def on_note_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if self._loading_note:
            return
        if previous:
            self.save_current_note()
        note_id = current.data(Qt.ItemDataRole.UserRole) if current else ""
        note = self.project.note_by_id(note_id)
        if note:
            self.load_note(note)

    def load_note(self, note: Note) -> None:
        self._loading_note = True
        self.current_note_id = note.id
        self.note_title.setText(note.title)
        category_index = self.note_category.findText(note.category)
        if category_index < 0:
            self.note_category.addItem(note.category)
            category_index = self.note_category.findText(note.category)
        self.note_category.setCurrentIndex(category_index if category_index >= 0 else 0)
        self.note_pin.setChecked(note.pinned)
        self.note_body.setPlainText(note.body)
        self.note_updated.setText(f"Actualizada {self.short_date(note.updated_at)}" if note.updated_at else "")
        self._loading_note = False
        self.update_note_stats()

    def clear_note_editor(self) -> None:
        if not hasattr(self, "note_title"):
            return
        self._loading_note = True
        self.current_note_id = ""
        self.note_title.clear()
        self.note_pin.setChecked(False)
        self.note_body.clear()
        self.note_updated.setText("")
        if self.note_category.count():
            self.note_category.setCurrentIndex(0)
        self._loading_note = False
        self.update_note_stats()

    def save_current_note(self) -> None:
        if not self.current_note_id or not hasattr(self, "note_title"):
            return
        note = self.project.note_by_id(self.current_note_id)
        if not note:
            return
        old_category = note.category
        note.title = self.note_title.text().strip() or "Nota sin titulo"
        note.category = self.note_category.currentText().strip() or "General"
        note.body = self.note_body.toPlainText()
        note.pinned = self.note_pin.isChecked()
        note.updated_at = now_iso()
        current = self.note_list.currentItem()
        if current:
            prefix = "[Fija] " if note.pinned else ""
            current.setText(f"{prefix}{note.title}\n{note.category} · {word_count(note.body)} palabras")
        self.note_updated.setText(f"Actualizada {self.short_date(note.updated_at)}")
        if old_category != note.category:
            self.refresh_note_categories()

    def add_note(self) -> None:
        self.save_current_note()
        title, ok = QInputDialog.getText(self, "Nueva nota", "Titulo")
        if not ok:
            return
        category = self.note_category_filter.currentData() or "General"
        note = Note(id=new_id("note"), title=title.strip() or f"Nota {len(self.project.notes) + 1}", category=category)
        self.project.notes.append(note)
        self.current_note_id = note.id
        self.refresh_note_categories()
        self.refresh_notes(save_current=False)
        self.mark_dirty()

    def delete_note(self) -> None:
        current = self.note_list.currentItem()
        if not current:
            return
        note_id = current.data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(self, "Eliminar nota", "Eliminar esta nota?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.project.notes = [item for item in self.project.notes if item.id != note_id]
        self.current_note_id = ""
        self.refresh_note_categories()
        self.refresh_notes(save_current=False)
        self.mark_dirty()

    def duplicate_note(self) -> None:
        self.save_current_note()
        note = self.project.note_by_id(self.current_note_id)
        if not note:
            return
        clone = copy.deepcopy(note)
        clone.id = new_id("note")
        clone.title = f"{note.title} copia"
        clone.created_at = now_iso()
        clone.updated_at = clone.created_at
        self.project.notes.append(clone)
        self.current_note_id = clone.id
        self.refresh_note_categories()
        self.refresh_notes(save_current=False)
        self.mark_dirty()

    def on_note_body_changed(self) -> None:
        self.update_note_stats()
        self.mark_dirty()

    def update_note_stats(self) -> None:
        if not hasattr(self, "note_words"):
            return
        text = self.note_body.toPlainText() if hasattr(self, "note_body") else ""
        self.note_words.set_values(str(word_count(text)), "Nota abierta")
        self.note_chars.set_values(str(len(text)), "")
        self.note_total.set_values(str(len(self.project.notes)), self.note_category_summary(self.project))

    def configure_image_list(self, widget: QListWidget) -> None:
        widget.setViewMode(QListView.ViewMode.IconMode)
        widget.setIconSize(QSize(92, 92))
        widget.setGridSize(QSize(112, 124))
        widget.setResizeMode(QListView.ResizeMode.Adjust)
        widget.setMovement(QListView.Movement.Static)
        widget.setWordWrap(True)

    def asset_list_item(self, relative_path: str) -> QListWidgetItem:
        item = QListWidgetItem(Path(relative_path).name)
        path = resolve_asset(self.project_dir, relative_path)
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            item.setIcon(QIcon(pixmap.scaled(92, 92, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
        else:
            item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        return item

    def preview_selected_asset(self, widget: QListWidget) -> None:
        current = widget.currentItem()
        if not current:
            return
        relative_path = current.data(Qt.ItemDataRole.UserRole)
        image_path = resolve_asset(self.project_dir, relative_path)
        dialog = ImagePreviewDialog(self, image_path)
        dialog.exec()

    def refresh_category_controls(self) -> None:
        self._loading_entity = True
        current_filter = self.entity_category_filter.currentData()
        current_editor = self.entity_category_combo.currentData()
        self.entity_category_filter.clear()
        self.entity_category_combo.clear()
        self.entity_category_filter.addItem("Todas", "")
        for category in self.project.categories:
            self.entity_category_filter.addItem(category.name, category.id)
            self.entity_category_combo.addItem(category.name, category.id)
        if current_filter:
            index = self.entity_category_filter.findData(current_filter)
            self.entity_category_filter.setCurrentIndex(index if index >= 0 else 0)
        if current_editor:
            index = self.entity_category_combo.findData(current_editor)
            self.entity_category_combo.setCurrentIndex(index if index >= 0 else 0)
        self._loading_entity = False

    def refresh_entities(self, *_args: Any, save_current: bool = True) -> None:
        if self._loading_entity:
            return
        if save_current:
            self.save_current_entity()
        category_id = self.entity_category_filter.currentData()
        query = self.entity_search.text().strip().lower() if hasattr(self, "entity_search") else ""
        self._loading_entity = True
        self.entity_list.clear()
        for entity in sorted(self.project.entities, key=lambda item: item.name.lower()):
            if category_id and entity.category_id != category_id:
                continue
            haystack = " ".join(
                [
                    entity.name,
                    entity.summary,
                    str(entity.fields),
                    self.project.category_by_id(entity.category_id).name if self.project.category_by_id(entity.category_id) else "",
                ]
            ).lower()
            if query and query not in haystack:
                continue
            category = self.project.category_by_id(entity.category_id)
            item = QListWidgetItem(f"{entity.name}\n{category.name if category else 'Sin categoria'}")
            item.setData(Qt.ItemDataRole.UserRole, entity.id)
            self.entity_list.addItem(item)
        self._loading_entity = False
        if self.entity_list.count():
            row = 0
            if self.current_entity_id:
                for index in range(self.entity_list.count()):
                    if self.entity_list.item(index).data(Qt.ItemDataRole.UserRole) == self.current_entity_id:
                        row = index
                        break
            self.entity_list.setCurrentRow(row)
            entity = self.project.entity_by_id(self.entity_list.item(row).data(Qt.ItemDataRole.UserRole))
            if entity:
                self.load_entity(entity)
        else:
            self.clear_entity_editor()

    def on_entity_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if self._loading_entity:
            return
        if previous:
            self.save_current_entity()
        entity_id = current.data(Qt.ItemDataRole.UserRole) if current else ""
        entity = self.project.entity_by_id(entity_id)
        if entity:
            self.load_entity(entity)

    def load_entity(self, entity: Entity) -> None:
        self._loading_entity = True
        self.current_entity_id = entity.id
        self.entity_name.setText(entity.name)
        self.entity_summary.setPlainText(entity.summary)
        index = self.entity_category_combo.findData(entity.category_id)
        self.entity_category_combo.setCurrentIndex(index if index >= 0 else 0)
        self.refresh_variant_combo(entity)
        self.build_dynamic_fields(entity)
        self.refresh_entity_photos(entity)
        self._loading_entity = False

    def clear_entity_editor(self) -> None:
        self._loading_entity = True
        self.current_entity_id = ""
        self.entity_name.clear()
        self.entity_summary.clear()
        self.entity_variant_combo.clear()
        self.clear_dynamic_fields()
        self.entity_photos.clear()
        self._loading_entity = False

    def save_current_entity(self) -> None:
        if not self.current_entity_id:
            return
        entity = self.project.entity_by_id(self.current_entity_id)
        if not entity:
            return
        entity.name = self.entity_name.text().strip() or "Entrada sin nombre"
        entity.summary = self.entity_summary.toPlainText().strip()
        entity.category_id = self.entity_category_combo.currentData() or entity.category_id
        entity.variant_id = self.entity_variant_combo.currentData() or ""
        for field_id, widget in self.field_widgets.items():
            entity.fields[field_id] = self.widget_value(widget)
        current = self.entity_list.currentItem()
        if current:
            category = self.project.category_by_id(entity.category_id)
            current.setText(f"{entity.name}\n{category.name if category else 'Sin categoria'}")

    def on_entity_category_changed(self, *_args: Any) -> None:
        if self._loading_entity:
            return
        entity = self.project.entity_by_id(self.current_entity_id)
        if entity:
            self.save_current_entity()
            entity.category_id = self.entity_category_combo.currentData() or entity.category_id
            entity.variant_id = ""
            self.refresh_variant_combo(entity)
            self.build_dynamic_fields(entity)
            self.mark_dirty()
            self.refresh_entities(save_current=False)

    def on_entity_variant_changed(self, *_args: Any) -> None:
        if self._loading_entity:
            return
        entity = self.project.entity_by_id(self.current_entity_id)
        if entity:
            self.save_current_entity()
            entity.variant_id = self.entity_variant_combo.currentData() or ""
            self.build_dynamic_fields(entity)
            self.mark_dirty()

    def refresh_variant_combo(self, entity: Entity) -> None:
        category = self.project.category_by_id(entity.category_id)
        self.entity_variant_combo.clear()
        self.entity_variant_combo.addItem("Sin variante", "")
        if category:
            for variant in category.variants:
                self.entity_variant_combo.addItem(variant.name, variant.id)
            label = category.variant_label or "Variante"
            self.entity_variant_combo.setToolTip(label)
        index = self.entity_variant_combo.findData(entity.variant_id)
        self.entity_variant_combo.setCurrentIndex(index if index >= 0 else 0)
        self.entity_variant_combo.setEnabled(bool(category and category.variants))

    def clear_dynamic_fields(self) -> None:
        while self.dynamic_fields_layout.rowCount():
            self.dynamic_fields_layout.removeRow(0)
        self.field_widgets.clear()

    def build_dynamic_fields(self, entity: Entity) -> None:
        self.clear_dynamic_fields()
        category = self.project.category_by_id(entity.category_id)
        if not category:
            return
        definitions = list(category.fields)
        variant = next((item for item in category.variants if item.id == entity.variant_id), None)
        if variant:
            header = QLabel(f"{category.variant_label or 'Variante'}: {variant.name}")
            header.setStyleSheet("color: #bfdbfe; font-weight: 700;")
            self.dynamic_fields_layout.addRow(header)
            definitions.extend(variant.fields)
        for definition in definitions:
            widget = self.widget_for_field(definition, entity.fields.get(definition.id))
            self.field_widgets[definition.id] = widget
            self.dynamic_fields_layout.addRow(definition.name, widget)

    def widget_for_field(self, definition: FieldDefinition, value: Any) -> QWidget:
        if definition.type == "long_text":
            widget = QTextEdit()
            widget.setAcceptRichText(False)
            widget.setMinimumHeight(90)
            widget.setPlainText(str(value or ""))
            widget.textChanged.connect(self.mark_dirty)
            return widget
        if definition.type == "number":
            widget = QLineEdit("" if value in (None, "") else str(value))
            widget.setValidator(QDoubleValidator(widget))
            widget.textChanged.connect(self.mark_dirty)
            return widget
        if definition.type == "date":
            widget = QDateEdit()
            widget.setCalendarPopup(True)
            date = QDate.fromString(str(value or ""), "yyyy-MM-dd")
            widget.setDate(date if date.isValid() else QDate.currentDate())
            widget.dateChanged.connect(self.mark_dirty)
            return widget
        if definition.type == "checkbox":
            widget = QCheckBox()
            widget.setChecked(bool(value))
            widget.toggled.connect(self.mark_dirty)
            return widget
        if definition.type == "choice":
            widget = QComboBox()
            for option in definition.options:
                widget.addItem(option)
            if value:
                index = widget.findText(str(value))
                widget.setCurrentIndex(index if index >= 0 else 0)
            widget.currentIndexChanged.connect(self.mark_dirty)
            return widget
        widget = QLineEdit(str(value or ""))
        widget.textChanged.connect(self.mark_dirty)
        return widget

    def widget_value(self, widget: QWidget) -> Any:
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, QDateEdit):
            return widget.date().toString("yyyy-MM-dd")
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        return ""

    def add_entity(self) -> None:
        category_id = self.entity_category_filter.currentData()
        if not category_id and self.project.categories:
            category_id = self.project.categories[0].id
        if not category_id:
            QMessageBox.warning(self, "Sin categorias", "Crea una categoria primero.")
            return
        name, ok = QInputDialog.getText(self, "Nueva entrada", "Nombre")
        if not ok:
            return
        entity = Entity(id=new_id("entity"), category_id=category_id, name=name.strip() or "Entrada sin nombre")
        self.project.entities.append(entity)
        self.current_entity_id = entity.id
        self.refresh_entities(save_current=False)
        self.mark_dirty()

    def duplicate_entity(self) -> None:
        self.save_current_entity()
        entity = self.project.entity_by_id(self.current_entity_id)
        if not entity:
            return
        clone = copy.deepcopy(entity)
        clone.id = new_id("entity")
        clone.name = f"{entity.name} copia"
        self.project.entities.append(clone)
        self.current_entity_id = clone.id
        if self.entity_category_filter.currentData() and self.entity_category_filter.currentData() != clone.category_id:
            self.entity_category_filter.blockSignals(True)
            self.entity_category_filter.setCurrentIndex(0)
            self.entity_category_filter.blockSignals(False)
        self.refresh_entities(save_current=False)
        self.mark_dirty()

    def delete_entity(self) -> None:
        current = self.entity_list.currentItem()
        if not current:
            return
        entity_id = current.data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(self, "Eliminar entrada", "Eliminar esta ficha del mundo?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.project.entities = [item for item in self.project.entities if item.id != entity_id]
        self.current_entity_id = ""
        self.refresh_entities(save_current=False)
        self.mark_dirty()

    def edit_schema(self) -> None:
        self.save_current_entity()
        dialog = SchemaDialog(self, self.project.categories)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.project.categories = dialog.categories
        valid_categories = {item.id for item in self.project.categories}
        default_category = self.project.categories[0].id if self.project.categories else ""
        for entity in self.project.entities:
            if entity.category_id not in valid_categories:
                entity.category_id = default_category
                entity.variant_id = ""
        self.refresh_category_controls()
        self.refresh_entities(save_current=False)
        self.mark_dirty()

    def refresh_entity_photos(self, entity: Entity) -> None:
        self.entity_photos.clear()
        for photo in entity.photos:
            item = self.asset_list_item(photo)
            item.setData(Qt.ItemDataRole.UserRole, photo)
            self.entity_photos.addItem(item)

    def add_entity_photos(self) -> None:
        entity = self.project.entity_by_id(self.current_entity_id)
        if not entity:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Asignar fotos", str(Path.home()), IMAGE_FILTER)
        if not paths:
            return
        for item in paths:
            entity.photos.append(copy_asset(self.project_dir, Path(item), "world"))
        self.refresh_entity_photos(entity)
        self.mark_dirty()

    def remove_entity_photo(self) -> None:
        entity = self.project.entity_by_id(self.current_entity_id)
        current = self.entity_photos.currentItem()
        if not entity or not current:
            return
        rel = current.data(Qt.ItemDataRole.UserRole)
        entity.photos = [item for item in entity.photos if item != rel]
        self.refresh_entity_photos(entity)
        self.mark_dirty()

    def set_cover_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Asignar portada", str(Path.home()), IMAGE_FILTER)
        if not path:
            return
        self.project.layout.cover_image = copy_asset(self.project_dir, Path(path), "cover")
        self.update_cover_preview()
        self.mark_dirty()

    def clear_cover_image(self) -> None:
        self.project.layout.cover_image = ""
        self.update_cover_preview()
        self.mark_dirty()

    def preview_cover_image(self) -> None:
        if not self.project.layout.cover_image:
            return
        dialog = ImagePreviewDialog(self, resolve_asset(self.project_dir, self.project.layout.cover_image))
        dialog.exec()

    def update_cover_preview(self) -> None:
        if not hasattr(self, "cover_label"):
            return
        cover = self.project.layout.cover_image
        if not cover:
            self.cover_label.setText("Sin imagen de portada")
            self.cover_preview.clear()
            self.cover_preview.setText("Portada no asignada")
            return
        self.cover_label.setText(Path(cover).name)
        pixmap = QPixmap(str(resolve_asset(self.project_dir, cover)))
        if pixmap.isNull():
            self.cover_preview.setText("No se pudo cargar la portada")
            return
        self.cover_preview.setPixmap(
            pixmap.scaled(230, 130, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )

    def update_pdf_preview(self) -> None:
        if not hasattr(self, "pdf_preview"):
            return
        self.save_current_chapter()
        self.save_current_note()
        self.save_current_entity()
        self.sync_project_from_ui()
        try:
            html = build_project_html(self.project, self.project_dir, 520)
        except Exception as exc:
            self.pdf_preview.setPlainText(f"No se pudo generar la vista previa: {exc}")
            return
        self.pdf_preview.setHtml(html)

    def refresh_live_panels(self) -> None:
        if self._refreshing_dashboard:
            return
        self._refreshing_dashboard = True
        try:
            self.update_dashboard()
            self.update_pdf_preview()
        finally:
            self._refreshing_dashboard = False

    def total_words(self) -> int:
        current = self.project.chapter_by_id(self.current_chapter_id)
        if current:
            current.body = self.chapter_body.toPlainText()
        return sum(word_count(chapter.body) for chapter in self.project.chapters)

    def total_images(self) -> int:
        chapter_images = sum(len(chapter.images) for chapter in self.project.chapters)
        entity_photos = sum(len(entity.photos) for entity in self.project.entities)
        cover = 1 if self.project.layout.cover_image else 0
        return chapter_images + entity_photos + cover

    def update_dashboard(self) -> None:
        if not hasattr(self, "stat_words"):
            return
        total_words = self.total_words()
        target = int(self.project_target.value()) if hasattr(self, "project_target") else self.project.target_words
        self.header_title.setText(self.project_title.text().strip() or self.project.title)
        self.header_meta.setText(
            f"{len(self.project.chapters)} capitulos · {len(self.project.notes)} notas · {len(self.project.entities)} fichas · {self.project_dir}"
        )
        self.header_words.setText(f"{total_words} palabras")
        self.stat_words.set_values(str(total_words), f"Objetivo: {target}")
        self.stat_chapters.set_values(str(len(self.project.chapters)), self.chapter_status_summary())
        self.stat_notes.set_values(str(len(self.project.notes)), self.note_category_summary())
        self.stat_world.set_values(str(len(self.project.entities)), f"{len(self.project.categories)} categorias")
        self.stat_assets.set_values(str(self.total_images()), "Portada, capitulos y fichas")
        self.project_progress.setValue(percent(total_words, target))
        self.project_progress_label.setText(f"{total_words} de {target} palabras ({percent(total_words, target)}%)")

        self.chapter_map.clear()
        for chapter in self.project.chapters:
            words = word_count(chapter.body)
            item = QTreeWidgetItem(
                [
                    chapter.title,
                    chapter.status,
                    str(words),
                    str(chapter.target_words),
                    chapter.pov,
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, chapter.id)
            self.chapter_map.addTopLevelItem(item)
        for column in range(self.chapter_map.columnCount()):
            self.chapter_map.resizeColumnToContents(column)

        self.category_stats.clear()
        for category in self.project.categories:
            entries = [entity for entity in self.project.entities if entity.category_id == category.id]
            item = QTreeWidgetItem(
                [
                    category.name,
                    str(len(entries)),
                    str(len(category.fields)),
                    str(len(category.variants)),
                ]
            )
            self.category_stats.addTopLevelItem(item)
        for column in range(self.category_stats.columnCount()):
            self.category_stats.resizeColumnToContents(column)
        self.perform_global_search()

    def chapter_status_summary(self, project: Project | None = None) -> str:
        project = project or self.project
        counts = {status: 0 for status in CHAPTER_STATUSES}
        for chapter in project.chapters:
            counts[chapter.status] = counts.get(chapter.status, 0) + 1
        parts = [f"{status}: {count}" for status, count in counts.items() if count]
        return " · ".join(parts) if parts else "Sin estado"

    def note_category_summary(self, project: Project | None = None) -> str:
        project = project or self.project
        counts: dict[str, int] = {}
        for note in project.notes:
            category = note.category or "General"
            counts[category] = counts.get(category, 0) + 1
        parts = [f"{name}: {count}" for name, count in sorted(counts.items(), key=lambda item: item[0].lower())]
        return " · ".join(parts) if parts else "Sin notas"

    def perform_global_search(self, *_args: Any) -> None:
        if not hasattr(self, "search_results"):
            return
        query = self.global_search.text().strip().lower()
        self.search_results.clear()
        if not query:
            return
        for chapter in self.project.chapters:
            haystack = "\n".join([chapter.title, chapter.summary, chapter.notes, chapter.body, chapter.pov, chapter.status])
            if query in haystack.lower():
                item = QTreeWidgetItem(["Capitulo", chapter.title, self.extract_snippet(haystack, query)])
                item.setData(0, Qt.ItemDataRole.UserRole, ("chapter", chapter.id))
                self.search_results.addTopLevelItem(item)
        for note in self.project.notes:
            haystack = "\n".join([note.title, note.category, note.body])
            if query in haystack.lower():
                item = QTreeWidgetItem(["Nota", note.title, self.extract_snippet(haystack, query)])
                item.setData(0, Qt.ItemDataRole.UserRole, ("note", note.id))
                self.search_results.addTopLevelItem(item)
        for entity in self.project.entities:
            category = self.project.category_by_id(entity.category_id)
            haystack = "\n".join([entity.name, entity.summary, str(entity.fields), category.name if category else ""])
            if query in haystack.lower():
                item = QTreeWidgetItem(["Ficha", entity.name, self.extract_snippet(haystack, query)])
                item.setData(0, Qt.ItemDataRole.UserRole, ("entity", entity.id))
                self.search_results.addTopLevelItem(item)
        for column in range(self.search_results.columnCount()):
            self.search_results.resizeColumnToContents(column)

    def extract_snippet(self, text: str, query: str) -> str:
        clean = " ".join((text or "").split())
        index = clean.lower().find(query)
        if index < 0:
            return clean[:120]
        start = max(0, index - 45)
        end = min(len(clean), index + len(query) + 75)
        prefix = "..." if start else ""
        suffix = "..." if end < len(clean) else ""
        return f"{prefix}{clean[start:end]}{suffix}"

    def open_chapter_from_map(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        chapter_id = item.data(0, Qt.ItemDataRole.UserRole)
        self.open_chapter(chapter_id)

    def open_search_result(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        kind, item_id = payload
        if kind == "chapter":
            self.open_chapter(item_id)
        elif kind == "note":
            self.open_note(item_id)
        elif kind == "entity":
            self.open_entity(item_id)

    def open_chapter(self, chapter_id: str) -> None:
        self.tabs.setCurrentIndex(2)
        self.chapter_search.clear()
        self.current_chapter_id = chapter_id
        self.refresh_chapters(save_current=False)
        for row in range(self.chapter_list.count()):
            if self.chapter_list.item(row).data(Qt.ItemDataRole.UserRole) == chapter_id:
                self.chapter_list.setCurrentRow(row)
                break

    def open_note(self, note_id: str) -> None:
        self.tabs.setCurrentIndex(3)
        self.note_search.clear()
        self.note_category_filter.blockSignals(True)
        self.note_category_filter.setCurrentIndex(0)
        self.note_category_filter.blockSignals(False)
        self.current_note_id = note_id
        self.refresh_notes(save_current=False)
        for row in range(self.note_list.count()):
            if self.note_list.item(row).data(Qt.ItemDataRole.UserRole) == note_id:
                self.note_list.setCurrentRow(row)
                break

    def open_entity(self, entity_id: str) -> None:
        self.tabs.setCurrentIndex(4)
        self.entity_search.clear()
        self.entity_category_filter.blockSignals(True)
        self.entity_category_filter.setCurrentIndex(0)
        self.entity_category_filter.blockSignals(False)
        self.current_entity_id = entity_id
        self.refresh_entities(save_current=False)
        for row in range(self.entity_list.count()):
            if self.entity_list.item(row).data(Qt.ItemDataRole.UserRole) == entity_id:
                self.entity_list.setCurrentRow(row)
                break

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self.save_now(show_message=False)
        except Exception as exc:
            answer = QMessageBox.question(
                self,
                "No se pudo guardar",
                f"No se pudo guardar antes de salir:\n{exc}\n\nSalir de todos modos?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()
