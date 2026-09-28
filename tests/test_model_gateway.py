"""
Tests for ModelGateway interface.
"""

import unittest

from core.model_gateway import ModelGateway
from core.model_router import ModelRouter


class TestModelGateway(unittest.TestCase):
    def test_cannot_instantiate_abc(self):
        with self.assertRaises(TypeError):
            ModelGateway()  # type: ignore

    def test_model_router_is_subclass(self):
        self.assertTrue(issubclass(ModelRouter, ModelGateway))
