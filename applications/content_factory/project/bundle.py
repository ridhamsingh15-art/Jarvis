"""
Project Bundle aggregate logic.
"""

import dataclasses
from datetime import datetime, timezone

from applications.content_factory.script_engine.models import ScriptPackage
from applications.content_factory.storyboard_engine.models import StoryboardPackage

from .models import Asset, ProjectBundle


class BundleModifier:
    """Helper for immutable updates to a ProjectBundle."""

    @staticmethod
    def update_timestamp(bundle: ProjectBundle) -> ProjectBundle:
        now = datetime.now(timezone.utc).isoformat()
        new_meta = dataclasses.replace(bundle.metadata, updated_at=now)
        return dataclasses.replace(bundle, metadata=new_meta)

    @staticmethod
    def set_script(bundle: ProjectBundle, script: ScriptPackage) -> ProjectBundle:
        b = dataclasses.replace(bundle, script_package=script)
        return BundleModifier.update_timestamp(b)

    @staticmethod
    def set_storyboard(bundle: ProjectBundle, storyboard: StoryboardPackage) -> ProjectBundle:
        b = dataclasses.replace(bundle, storyboard_package=storyboard)
        return BundleModifier.update_timestamp(b)

    @staticmethod
    def add_asset(bundle: ProjectBundle, asset: Asset) -> ProjectBundle:
        assets = list(bundle.assets)
        # If updating an asset, we might want to keep the old ones for history, or just append it.
        # Since it's versioned, we append it.
        assets.append(asset)
        b = dataclasses.replace(bundle, assets=assets)
        return BundleModifier.update_timestamp(b)

    @staticmethod
    def add_mission(bundle: ProjectBundle, mission_id: str) -> ProjectBundle:
        if mission_id in bundle.mission_history:
            return bundle
        history = list(bundle.mission_history)
        history.append(mission_id)
        b = dataclasses.replace(bundle, mission_history=history)
        return BundleModifier.update_timestamp(b)

    @staticmethod
    def get_asset(bundle: ProjectBundle, asset_id: str) -> Asset | None:
        # Return the latest version matching the asset_id
        matches = [a for a in bundle.assets if a.metadata.asset_id == asset_id]
        if not matches:
            return None
        matches.sort(key=lambda a: a.metadata.version, reverse=True)
        return matches[0]

    @staticmethod
    def get_assets_by_type(bundle: ProjectBundle, asset_type: str) -> list[Asset]:
        # Return only the latest versions for each asset_id of the given type
        matches = [a for a in bundle.assets if a.metadata.asset_type == asset_type]
        latest = {}
        for a in matches:
            aid = a.metadata.asset_id
            if aid not in latest or latest[aid].metadata.version < a.metadata.version:
                latest[aid] = a
        return list(latest.values())
