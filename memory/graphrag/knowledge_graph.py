"""
GraphRAG Knowledge Graph
Graph-based retrieval augmented generation for robot memory
"""

from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """
    Knowledge Graph for Robot Memory using Neo4j
    Implements GraphRAG for spatial and temporal reasoning
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j connection

        Args:
            uri: Neo4j connection URI
            user: Database username
            password: Database password
        """
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Connected to Neo4j at {uri}")

    async def close(self):
        """Close database connection"""
        await self.driver.close()

    async def add_entity(self, entity_type: str, name: str, properties: Dict[str, Any]) -> str:
        """
        Add entity to knowledge graph

        Args:
            entity_type: Type of entity (e.g., 'Object', 'Location', 'Person')
            name: Entity name/identifier
            properties: Additional properties

        Returns:
            Entity ID
        """
        async with self.driver.session() as session:
            query = f"""
            MERGE (e:{entity_type} {{name: $name}})
            SET e += $properties
            SET e.last_updated = timestamp()
            RETURN id(e) as entity_id
            """

            result = await session.run(
                query,
                name=name,
                properties=properties
            )

            record = await result.single()
            entity_id = record["entity_id"] if record else None

            logger.info(f"Added entity: {entity_type}:{name}")
            return str(entity_id)

    async def add_relationship(
        self,
        from_entity: str,
        to_entity: str,
        relationship_type: str,
        properties: Dict[str, Any] = None
    ):
        """
        Add relationship between entities

        Args:
            from_entity: Source entity name
            to_entity: Target entity name
            relationship_type: Type of relationship (e.g., 'ON', 'IN', 'NEAR')
            properties: Additional properties
        """
        async with self.driver.session() as session:
            query = f"""
            MATCH (a {{name: $from_entity}})
            MATCH (b {{name: $to_entity}})
            MERGE (a)-[r:{relationship_type}]->(b)
            SET r += $properties
            SET r.timestamp = timestamp()
            """

            await session.run(
                query,
                from_entity=from_entity,
                to_entity=to_entity,
                properties=properties or {}
            )

            logger.info(f"Added relationship: {from_entity} -{relationship_type}-> {to_entity}")

    async def query_graph(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Query knowledge graph with natural language

        Args:
            query: Natural language query
            limit: Maximum results

        Returns:
            List of relevant facts
        """
        # Convert natural language to Cypher query
        # In production, use NLP to generate Cypher
        # For now, use pattern matching

        results = []

        if "where" in query.lower():
            # Location query
            results = await self._find_location_query(query, limit)
        elif "when" in query.lower():
            # Temporal query
            results = await self._find_temporal_query(query, limit)
        else:
            # General query
            results = await self._general_query(query, limit)

        return results

    async def _find_location_query(self, query: str, limit: int) -> List[Dict]:
        """Find location of entities"""
        async with self.driver.session() as session:
            cypher_query = """
            MATCH (obj)-[:ON|IN|NEAR*1..2]->(loc:Location)
            RETURN obj.name as object, loc.name as location, labels(obj) as type
            LIMIT $limit
            """

            result = await session.run(cypher_query, limit=limit)

            facts = []
            async for record in result:
                facts.append({
                    "object": record["object"],
                    "location": record["location"],
                    "type": record["type"]
                })

            return facts

    async def _find_temporal_query(self, query: str, limit: int) -> List[Dict]:
        """Find temporal information"""
        async with self.driver.session() as session:
            cypher_query = """
            MATCH (e)-[r]->(target)
            WHERE exists(r.timestamp)
            RETURN e.name as entity, type(r) as relation, target.name as target,
                   r.timestamp as timestamp
            ORDER BY r.timestamp DESC
            LIMIT $limit
            """

            result = await session.run(cypher_query, limit=limit)

            facts = []
            async for record in result:
                facts.append({
                    "entity": record["entity"],
                    "relation": record["relation"],
                    "target": record["target"],
                    "timestamp": record["timestamp"]
                })

            return facts

    async def _general_query(self, query: str, limit: int) -> List[Dict]:
        """General graph query"""
        async with self.driver.session() as session:
            cypher_query = """
            MATCH (e)-[r]->(target)
            RETURN e.name as entity, type(r) as relation, target.name as target
            LIMIT $limit
            """

            result = await session.run(cypher_query, limit=limit)

            facts = []
            async for record in result:
                facts.append({
                    "entity": record["entity"],
                    "relation": record["relation"],
                    "target": record["target"]
                })

            return facts

    async def update_world_state(self, observations: List[Dict]):
        """
        Update knowledge graph with new observations

        Args:
            observations: List of observed facts
        """
        for obs in observations:
            if obs.get("type") == "object_location":
                # Add object
                await self.add_entity(
                    "Object",
                    obs["object_name"],
                    {"class": obs.get("class", "unknown")}
                )

                # Add location
                await self.add_entity(
                    "Location",
                    obs["location"],
                    {}
                )

                # Add relationship
                await self.add_relationship(
                    obs["object_name"],
                    obs["location"],
                    "ON",
                    {"confidence": obs.get("confidence", 1.0)}
                )

    async def get_spatial_context(self, location: str) -> Dict[str, Any]:
        """
        Get spatial context for a location

        Args:
            location: Location name

        Returns:
            Context with nearby objects and connected locations
        """
        async with self.driver.session() as session:
            query = """
            MATCH (loc:Location {name: $location})
            OPTIONAL MATCH (obj)-[:ON|IN]->(loc)
            OPTIONAL MATCH (loc)-[:CONNECTS_TO]-(other:Location)
            RETURN loc, collect(DISTINCT obj.name) as objects,
                   collect(DISTINCT other.name) as connected_locations
            """

            result = await session.run(query, location=location)
            record = await result.single()

            if record:
                return {
                    "location": location,
                    "objects": record["objects"],
                    "connected_locations": record["connected_locations"]
                }

            return {"location": location, "objects": [], "connected_locations": []}


# Example usage
if __name__ == "__main__":
    import asyncio
    import os

    async def main():
        kg = KnowledgeGraph(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password")
        )

        # Add some test data
        await kg.add_entity("Object", "red_bottle", {"color": "red", "type": "bottle"})
        await kg.add_entity("Location", "left_table", {"room": "kitchen"})
        await kg.add_relationship("red_bottle", "left_table", "ON")

        # Query
        results = await kg.query_graph("where is the red bottle?")
        print(f"Query results: {results}")

        await kg.close()

    asyncio.run(main())
