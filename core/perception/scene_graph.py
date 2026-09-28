"""
Scene Graph Builder.

Constructs a spatial and relational graph from a flat list of observations.
Determines relationships like "contains", "next to", or "above" based on
bounding box geometry.
"""
import logging
from core.perception.models import SceneGraph, PerceptionObservation, ObservationType

logger = logging.getLogger(__name__)

class SceneGraphBuilder:
    """Builds a relational SceneGraph from perception observations."""

    def build(self, observations: list[PerceptionObservation]) -> SceneGraph:
        """
        Analyze spatial bounds of observations to build a SceneGraph.
        """
        relationships = []
        
        # Simple O(N^2) geometric analysis for small N
        for i, obs_a in enumerate(observations):
            if not obs_a.bounds:
                continue
            for j, obs_b in enumerate(observations):
                if i == j or not obs_b.bounds:
                    continue
                    
                relation = self._determine_relationship(obs_a, obs_b)
                if relation:
                    relationships.append((obs_a.observation_id, relation, obs_b.observation_id))
                    
        return SceneGraph(type=ObservationType.SCENE, confidence=1.0, observations=observations, relationships=relationships)

    def _determine_relationship(self, obs_a: PerceptionObservation, obs_b: PerceptionObservation) -> str | None:
        """
        Determine spatial relationship of obs_b relative to obs_a.
        E.g., if obs_a fully encloses obs_b, returns "contains".
        """
        if not obs_a.bounds or not obs_b.bounds:
            return None
            
        a = obs_a.bounds
        b = obs_b.bounds
        
        # Contains: B is strictly inside A
        if (a.x <= b.x and a.y <= b.y and 
            a.x + a.width >= b.x + b.width and 
            a.y + a.height >= b.y + b.height):
            return "contains"
            
        # Above: B is below A, but horizontally aligned
        if b.y >= a.y + a.height and abs(a.x - b.x) < 0.1:
            return "is above" # From perspective of B, A is above B? Wait. A is above B.
            
        return None
