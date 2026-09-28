"""
Multimodal Perception Engine — Data Models.

Immutable, high-level representations of visual information extracted
from raw pixels, ready for cognitive reasoning.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional


class ObservationType(StrEnum):
    TEXT      = "text"
    UI        = "ui"
    DOCUMENT  = "document"
    SCENE     = "scene"
    IMAGE     = "image"


class UIComponentRole(StrEnum):
    BUTTON     = "button"
    MENU       = "menu"
    DIALOG     = "dialog"
    EDITOR     = "editor"
    TERMINAL   = "terminal"
    BROWSER    = "browser"
    ERROR      = "error"
    WARNING    = "warning"
    INFO       = "info"
    UNKNOWN    = "unknown"


@dataclass(frozen=True)
class SpatialBounds:
    """Bounding box coordinates (normalized 0.0 - 1.0 or absolute)."""
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, kw_only=True)
class PerceptionObservation:
    """Base class for all semantic observations."""
    type: ObservationType
    confidence: float
    bounds: Optional[SpatialBounds] = None
    observation_id: str = field(default_factory=lambda: f"obs_{uuid.uuid4().hex[:8]}")


@dataclass(frozen=True, kw_only=True)
class TextObservation(PerceptionObservation):
    """Extracted text preserving meaning and layout hints."""
    text: str
    is_heading: bool = False
    is_code: bool = False
    language: str = "unknown"
    font_size_hint: str = "normal"  # 'small', 'normal', 'large'


@dataclass(frozen=True, kw_only=True)
class UIObservation(PerceptionObservation):
    """Semantic UI element understood by the agent."""
    role: UIComponentRole
    label: str
    state: str = "default"  # 'active', 'disabled', 'focused', etc.
    interactive: bool = True
    context: str = ""       # surrounding context (e.g. parent window name)


@dataclass(frozen=True, kw_only=True)
class DocumentObservation(PerceptionObservation):
    """High-level document structure."""
    document_type: str      # 'report', 'invoice', 'receipt', 'paper'
    title: str
    summary: str
    key_value_pairs: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class ImageObservation(PerceptionObservation):
    """General understanding of an image, chart, or diagram."""
    description: str
    main_subjects: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class SceneGraph(PerceptionObservation):
    """Relational map of observations in a spatial layout."""
    observations: list[PerceptionObservation] = field(default_factory=list)
    relationships: list[tuple[str, str, str]] = field(default_factory=list) # (obs_id, relation, obs_id) e.g. ("A", "contains", "B")

    def format_for_prompt(self) -> str:
        """Serialise the scene graph into a text summary for the LLM."""
        lines = ["## Visual Perception Summary"]
        
        ui_elems = [o for o in self.observations if isinstance(o, UIObservation)]
        if ui_elems:
            lines.append("\n### User Interface Elements")
            for ui in ui_elems:
                status = f"[{ui.state}]" if ui.state != "default" else ""
                lines.append(f"- {ui.role.value.capitalize()} '{ui.label}' {status} (id: {ui.observation_id})")

        text_elems = [o for o in self.observations if isinstance(o, TextObservation)]
        if text_elems:
            lines.append("\n### Extracted Text")
            for t in text_elems:
                marker = "# " if t.is_heading else ("```\n" if t.is_code else "")
                end_marker = "\n```" if t.is_code else ""
                lines.append(f"{marker}{t.text}{end_marker}")
                
        doc_elems = [o for o in self.observations if isinstance(o, DocumentObservation)]
        if doc_elems:
            lines.append("\n### Document Data")
            for doc in doc_elems:
                lines.append(f"- Type: {doc.document_type.capitalize()}")
                lines.append(f"- Title: {doc.title}")
                for k, v in doc.key_value_pairs.items():
                    lines.append(f"  - {k}: {v}")

        img_elems = [o for o in self.observations if isinstance(o, ImageObservation)]
        if img_elems:
            lines.append("\n### Image Content")
            for img in img_elems:
                lines.append(f"- {img.description}")
                if img.tags:
                    lines.append(f"  - Tags: {', '.join(img.tags)}")

        if self.relationships:
            lines.append("\n### Spatial Relationships")
            for source_id, relation, target_id in self.relationships:
                lines.append(f"- {source_id} {relation} {target_id}")

        return "\n".join(lines)
