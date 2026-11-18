from __future__ import annotations

import tempfile
from pathlib import Path

from angryrest.application.services.collection_service import CollectionService
from angryrest.application.viewmodels.collections_viewmodel import CollectionsViewModel
from angryrest.infrastructure.storage.json_storage import JsonStorageAdapter


class TestBootstrapImports:
    def test_bootstrap_module_can_be_imported(self) -> None:
        from angryrest.ui.bootstrap import Theme, bootstrap_engine

        assert Theme is not None
        assert bootstrap_engine is not None

    def test_app_module_can_be_imported(self) -> None:
        from angryrest.app import main

        assert main is not None

    def test_theme_has_expected_properties(self) -> None:
        from angryrest.ui.bootstrap import Theme

        theme = Theme()
        assert theme.property("bgPrimary") == "#1e1e1e"
        assert theme.property("textPrimary") == "#d4d4d4"
        assert theme.property("methodGet") == "#4ec9b0"
        assert theme.property("status2xx") == "#4ec9b0"