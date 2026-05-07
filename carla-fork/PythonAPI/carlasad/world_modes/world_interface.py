"""
WorldInterface — abstract base for both world modes.

Both EditorWorld and ReconstructedWorld implement this interface.
Consumers (bridge, API, logging) only interact with WorldInterface.
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from ..layers.terrain_layer import TerrainLayer
from ..layers.process_layer import ProcessLayer


class WorldInterface(ABC):

    @property
    @abstractmethod
    def mode(self) -> str:
        """'editor' or 'reconstructed'"""
        ...

    @property
    @abstractmethod
    def map_name(self) -> str:
        ...

    @property
    @abstractmethod
    def terrain(self) -> TerrainLayer:
        ...

    @property
    @abstractmethod
    def process(self) -> ProcessLayer:
        ...

    @abstractmethod
    def get_metadata(self) -> dict:
        """Return world manifest metadata for logging."""
        ...

    @abstractmethod
    def load(self, carla_world) -> None:
        """Apply world configuration to running CARLA world."""
        ...


class EditorWorld(WorldInterface):
    """
    World assembled manually in Unreal Editor.
    Terrain semantics come from UE semantic paint + config YAML.
    """

    def __init__(self, map_name: str, terrain_config: Optional[str] = None):
        self._map_name = map_name
        self._terrain = TerrainLayer()
        self._process = ProcessLayer()
        self._terrain_config = terrain_config

    @property
    def mode(self) -> str:
        return "editor"

    @property
    def map_name(self) -> str:
        return self._map_name

    @property
    def terrain(self) -> TerrainLayer:
        return self._terrain

    @property
    def process(self) -> ProcessLayer:
        return self._process

    def get_metadata(self) -> dict:
        return {
            "mode": "editor",
            "map_name": self._map_name,
            "terrain_config": self._terrain_config,
        }

    def load(self, carla_world) -> None:
        if self._terrain_config:
            self._terrain.load_from_map(self._terrain_config)
        # TODO: apply semantic layer to CARLA world


class ReconstructedWorld(WorldInterface):
    """
    World reconstructed from real data: photo/video → SfM → GS → mesh → CARLA.
    """

    def __init__(self, map_name: str, reconstruction_path: str):
        self._map_name = map_name
        self._reconstruction_path = reconstruction_path
        self._terrain = TerrainLayer()
        self._process = ProcessLayer()

    @property
    def mode(self) -> str:
        return "reconstructed"

    @property
    def map_name(self) -> str:
        return self._map_name

    @property
    def terrain(self) -> TerrainLayer:
        return self._terrain

    @property
    def process(self) -> ProcessLayer:
        return self._process

    def get_metadata(self) -> dict:
        return {
            "mode": "reconstructed",
            "map_name": self._map_name,
            "reconstruction_path": self._reconstruction_path,
        }

    def load(self, carla_world) -> None:
        # TODO: load from reconstruction artifacts
        pass
