"""
Database connection managers
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from motor.motor_asyncio import AsyncIOMotorClient
from neo4j import AsyncGraphDatabase
import redis.asyncio as aioredis
from typing import Optional
import logging

from api.utils.config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy Base
Base = declarative_base()

# Global database clients
postgres_engine = None
postgres_session_maker = None
mongodb_client: Optional[AsyncIOMotorClient] = None
neo4j_driver = None
redis_client = None


async def init_databases():
    """Initialize all database connections"""
    global postgres_engine, postgres_session_maker, mongodb_client, neo4j_driver, redis_client

    # PostgreSQL with asyncpg
    try:
        postgres_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
        postgres_engine = create_async_engine(postgres_url, echo=settings.DEBUG)
        postgres_session_maker = async_sessionmaker(
            postgres_engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("PostgreSQL connection established")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")

    # MongoDB
    try:
        mongodb_client = AsyncIOMotorClient(settings.MONGODB_URI)
        # Test connection
        await mongodb_client.admin.command('ping')
        logger.info("MongoDB connection established")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")

    # Neo4j
    try:
        neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        # Test connection
        async with neo4j_driver.session() as session:
            await session.run("RETURN 1")
        logger.info("Neo4j connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")

    # Redis
    try:
        redis_client = await aioredis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")


async def close_databases():
    """Close all database connections"""
    global postgres_engine, mongodb_client, neo4j_driver, redis_client

    if postgres_engine:
        await postgres_engine.dispose()
        logger.info("PostgreSQL connection closed")

    if mongodb_client:
        mongodb_client.close()
        logger.info("MongoDB connection closed")

    if neo4j_driver:
        await neo4j_driver.close()
        logger.info("Neo4j connection closed")

    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


async def get_postgres_session() -> AsyncSession:
    """Get PostgreSQL session"""
    async with postgres_session_maker() as session:
        yield session


def get_mongodb():
    """Get MongoDB database"""
    return mongodb_client[settings.MONGODB_DB]


def get_neo4j_driver():
    """Get Neo4j driver"""
    return neo4j_driver


def get_redis():
    """Get Redis client"""
    return redis_client
