"""
Tests for the Multimodal Perception Engine.
"""
import pytest
from core.perception.models import (
    SceneGraph, SpatialBounds, TextObservation, UIObservation, 
    UIComponentRole, ObservationType, DocumentObservation
)
from core.perception.ocr import OCRPerception
from core.perception.ui_understanding import UIUnderstanding
from core.perception.scene_graph import SceneGraphBuilder
from core.vision.models import OCRResult, BoundingBox, UIElement
from core.vision.enums import UIElementType

class TestOCRPerception:
    def test_extract_text_observations(self):
        ocr = OCRPerception()
        
        raw_results = [
            # A heading (needs to be relatively tall compared to width for heuristic, and height > 0.05)
            # image_height = 1000, so 60 / 1000 = 0.06 > 0.05
            OCRResult(text="Main Menu", bounding_box=BoundingBox(0, 0, 100, 60), confidence=0.9),
            # Some code
            OCRResult(text="def foo():\n    return 42", bounding_box=BoundingBox(0, 30, 200, 50), confidence=0.9),
            # Normal text
            OCRResult(text="This is a normal paragraph of text.", bounding_box=BoundingBox(0, 90, 300, 20), confidence=0.9)
        ]
        
        obs = ocr.extract_text_observations(raw_results, 1000, 1000)
        assert len(obs) == 3
        
        assert obs[0].is_heading is True
        assert obs[0].font_size_hint == "large"
        
        assert obs[1].is_code is True
        
        assert obs[2].is_heading is False
        assert obs[2].is_code is False

class TestUIUnderstanding:
    def test_analyze_ui_elements(self):
        ui = UIUnderstanding()
        
        raw_elements = [
            UIElement(type=UIElementType.BUTTON, text="Submit", bounding_box=BoundingBox(0, 0, 100, 30), state={"status": "active"}),
            UIElement(type=UIElementType.WINDOW, text="bash - Terminal", bounding_box=BoundingBox(0, 50, 500, 400)),
            UIElement(type=UIElementType.STATUS_BAR, text="Connection failed with error code 500.", bounding_box=BoundingBox(0, 500, 300, 20))
        ]
        
        obs = ui.analyze_ui_elements(raw_elements, 1000, 1000)
        assert len(obs) == 3
        
        assert obs[0].role == UIComponentRole.BUTTON
        assert obs[0].state == "active"
        
        assert obs[1].role == UIComponentRole.TERMINAL
        
        assert obs[2].role == UIComponentRole.ERROR

class TestSceneGraphBuilder:
    def test_scene_graph_contains_relationship(self):
        builder = SceneGraphBuilder()
        
        obs_a = UIObservation(
            observation_id="win1", type=ObservationType.UI, confidence=1.0,
            bounds=SpatialBounds(0.0, 0.0, 0.5, 0.5), role=UIComponentRole.DIALOG, label="Dialog"
        )
        
        obs_b = UIObservation(
            observation_id="btn1", type=ObservationType.UI, confidence=1.0,
            bounds=SpatialBounds(0.1, 0.1, 0.1, 0.1), role=UIComponentRole.BUTTON, label="OK"
        )
        
        obs_c = UIObservation(
            observation_id="btn2", type=ObservationType.UI, confidence=1.0,
            bounds=SpatialBounds(0.6, 0.6, 0.1, 0.1), role=UIComponentRole.BUTTON, label="Cancel"
        )
        
        graph = builder.build([obs_a, obs_b, obs_c])
        
        assert len(graph.observations) == 3
        
        # win1 should contain btn1, but not btn2
        contains_rel = [r for r in graph.relationships if r[0] == "win1" and r[1] == "contains"]
        assert len(contains_rel) == 1
        assert contains_rel[0][2] == "btn1"

    def test_scene_graph_formatting(self):
        builder = SceneGraphBuilder()
        
        btn = UIObservation(
            observation_id="btn", type=ObservationType.UI, confidence=1.0,
            bounds=None, role=UIComponentRole.BUTTON, label="Click Me", state="focused"
        )
        
        text = TextObservation(
            observation_id="txt", type=ObservationType.TEXT, confidence=1.0,
            bounds=None, text="Hello World", is_heading=True
        )
        
        doc = DocumentObservation(
            observation_id="doc", type=ObservationType.DOCUMENT, confidence=1.0,
            bounds=None, document_type="invoice", title="Invoice #123", summary="Total $500",
            key_value_pairs={"Total": "$500"}
        )
        
        graph = builder.build([btn, text, doc])
        prompt = graph.format_for_prompt()
        
        assert "## Visual Perception Summary" in prompt
        assert "Button 'Click Me' [focused]" in prompt
        assert "# Hello World" in prompt
        assert "Invoice #123" in prompt
        assert "Total: $500" in prompt
