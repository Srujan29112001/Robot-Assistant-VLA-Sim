"""
Production Secrets Management
Secure handling of API keys, passwords, and sensitive configuration
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Secure secrets management for production deployment

    Features:
    - Environment variable integration
    - Encrypted local storage (for development)
    - AWS Secrets Manager integration (optional)
    - GCP Secret Manager integration (optional)
    - Azure Key Vault integration (optional)
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize secrets manager

        Args:
            encryption_key: Optional encryption key (from env or generated)
        """
        self.encryption_key = encryption_key or os.getenv("SECRETS_ENCRYPTION_KEY")

        if not self.encryption_key:
            # Generate from machine-specific seed (NOT for production!)
            logger.warning("No encryption key provided, using derived key (development only)")
            self.encryption_key = self._generate_machine_key()

        # Initialize cipher
        self.cipher = Fernet(self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key)

        # Secrets cache
        self._secrets_cache: Dict[str, str] = {}

        # Load from environment
        self._load_from_environment()

    def _generate_machine_key(self) -> bytes:
        """Generate a machine-specific encryption key (DEV ONLY)"""
        # Use machine hostname as seed (NOT secure for production!)
        import socket
        hostname = socket.gethostname()

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'robot-assistant-salt',  # Fixed salt for consistency
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(hostname.encode()))
        return key

    def _load_from_environment(self):
        """Load secrets from environment variables"""
        # List of expected secrets
        secret_keys = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "NEO4J_PASSWORD",
            "POSTGRES_PASSWORD",
            "MONGODB_PASSWORD",
            "REDIS_PASSWORD",
            "JWT_SECRET_KEY",
            "MLFLOW_TRACKING_URI",
            "WANDB_API_KEY",
        ]

        for key in secret_keys:
            value = os.getenv(key)
            if value:
                self._secrets_cache[key] = value
                logger.debug(f"Loaded secret: {key}")

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get secret by key

        Args:
            key: Secret key name
            default: Default value if not found

        Returns:
            Secret value or default
        """
        # Check cache first
        if key in self._secrets_cache:
            return self._secrets_cache[key]

        # Try environment
        env_value = os.getenv(key)
        if env_value:
            self._secrets_cache[key] = env_value
            return env_value

        # Try cloud providers (if configured)
        cloud_value = self._get_from_cloud(key)
        if cloud_value:
            self._secrets_cache[key] = cloud_value
            return cloud_value

        # Try encrypted local file
        file_value = self._get_from_file(key)
        if file_value:
            return file_value

        logger.warning(f"Secret not found: {key}")
        return default

    def set_secret(self, key: str, value: str, persist: bool = False):
        """
        Set secret value

        Args:
            key: Secret key
            value: Secret value
            persist: Whether to persist to encrypted file
        """
        self._secrets_cache[key] = value

        if persist:
            self._save_to_file(key, value)

    def _get_from_cloud(self, key: str) -> Optional[str]:
        """
        Get secret from cloud provider

        Tries AWS Secrets Manager, GCP Secret Manager, Azure Key Vault
        """
        # Try AWS Secrets Manager
        aws_value = self._get_from_aws(key)
        if aws_value:
            return aws_value

        # Try GCP Secret Manager
        gcp_value = self._get_from_gcp(key)
        if gcp_value:
            return gcp_value

        # Try Azure Key Vault
        azure_value = self._get_from_azure(key)
        if azure_value:
            return azure_value

        return None

    def _get_from_aws(self, key: str) -> Optional[str]:
        """Get secret from AWS Secrets Manager"""
        try:
            import boto3
            from botocore.exceptions import ClientError

            session = boto3.session.Session()
            client = session.client(
                service_name='secretsmanager',
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )

            try:
                response = client.get_secret_value(SecretId=key)
                return response['SecretString']
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    logger.warning(f"AWS Secrets Manager error: {e}")
                return None

        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"AWS Secrets Manager not available: {e}")
            return None

    def _get_from_gcp(self, key: str) -> Optional[str]:
        """Get secret from GCP Secret Manager"""
        try:
            from google.cloud import secretmanager

            client = secretmanager.SecretManagerServiceClient()
            project_id = os.getenv('GCP_PROJECT_ID')

            if not project_id:
                return None

            name = f"projects/{project_id}/secrets/{key}/versions/latest"

            try:
                response = client.access_secret_version(request={"name": name})
                return response.payload.data.decode('UTF-8')
            except Exception as e:
                logger.debug(f"GCP Secret not found: {key}")
                return None

        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"GCP Secret Manager not available: {e}")
            return None

    def _get_from_azure(self, key: str) -> Optional[str]:
        """Get secret from Azure Key Vault"""
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential

            vault_url = os.getenv('AZURE_KEY_VAULT_URL')
            if not vault_url:
                return None

            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_url, credential=credential)

            try:
                secret = client.get_secret(key)
                return secret.value
            except Exception as e:
                logger.debug(f"Azure secret not found: {key}")
                return None

        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"Azure Key Vault not available: {e}")
            return None

    def _get_from_file(self, key: str) -> Optional[str]:
        """Get secret from encrypted local file"""
        secrets_file = Path.home() / ".robot_secrets"

        if not secrets_file.exists():
            return None

        try:
            with open(secrets_file, 'rb') as f:
                encrypted_data = f.read()

            decrypted_data = self.cipher.decrypt(encrypted_data)
            secrets = json.loads(decrypted_data.decode())

            return secrets.get(key)

        except Exception as e:
            logger.error(f"Error reading encrypted secrets file: {e}")
            return None

    def _save_to_file(self, key: str, value: str):
        """Save secret to encrypted local file"""
        secrets_file = Path.home() / ".robot_secrets"

        # Load existing secrets
        secrets = {}
        if secrets_file.exists():
            try:
                with open(secrets_file, 'rb') as f:
                    encrypted_data = f.read()
                decrypted_data = self.cipher.decrypt(encrypted_data)
                secrets = json.loads(decrypted_data.decode())
            except:
                pass

        # Update secret
        secrets[key] = value

        # Encrypt and save
        try:
            encrypted_data = self.cipher.encrypt(json.dumps(secrets).encode())

            with open(secrets_file, 'wb') as f:
                f.write(encrypted_data)

            # Set restrictive permissions
            secrets_file.chmod(0o600)

            logger.info(f"Secret saved to encrypted file: {key}")

        except Exception as e:
            logger.error(f"Error saving secret to file: {e}")

    def get_database_url(self, service: str) -> str:
        """
        Get complete database connection URL

        Args:
            service: Database service (postgres, neo4j, mongodb, redis)

        Returns:
            Connection URL with credentials
        """
        if service == "postgres":
            password = self.get_secret("POSTGRES_PASSWORD", "postgres")
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            db = os.getenv("POSTGRES_DB", "robot_assistant")
            user = os.getenv("POSTGRES_USER", "postgres")
            return f"postgresql://{user}:{password}@{host}:{port}/{db}"

        elif service == "neo4j":
            password = self.get_secret("NEO4J_PASSWORD", "password")
            host = os.getenv("NEO4J_HOST", "localhost")
            port = os.getenv("NEO4J_PORT", "7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            return f"neo4j://{user}:{password}@{host}:{port}"

        elif service == "mongodb":
            password = self.get_secret("MONGODB_PASSWORD", "password")
            host = os.getenv("MONGODB_HOST", "localhost")
            port = os.getenv("MONGODB_PORT", "27017")
            user = os.getenv("MONGODB_USER", "root")
            db = os.getenv("MONGODB_DB", "robot_assistant")
            return f"mongodb://{user}:{password}@{host}:{port}/{db}"

        elif service == "redis":
            password = self.get_secret("REDIS_PASSWORD", "")
            host = os.getenv("REDIS_HOST", "localhost")
            port = os.getenv("REDIS_PORT", "6379")
            if password:
                return f"redis://:{password}@{host}:{port}/0"
            return f"redis://{host}:{port}/0"

        else:
            raise ValueError(f"Unknown database service: {service}")

    def rotate_secret(self, key: str, new_value: str):
        """
        Rotate a secret (update with new value)

        Args:
            key: Secret key
            new_value: New secret value
        """
        # Save old value for rollback
        old_value = self.get_secret(key)

        try:
            # Set new value
            self.set_secret(key, new_value, persist=True)

            # Update in cloud (if configured)
            self._update_cloud_secret(key, new_value)

            logger.info(f"Secret rotated: {key}")

        except Exception as e:
            # Rollback on error
            if old_value:
                self.set_secret(key, old_value, persist=True)
            logger.error(f"Secret rotation failed: {e}")
            raise

    def _update_cloud_secret(self, key: str, value: str):
        """Update secret in cloud providers"""
        # Implementation depends on cloud provider APIs
        # This is a placeholder for production implementation
        pass

    def validate_secrets(self) -> Dict[str, bool]:
        """
        Validate all required secrets are present

        Returns:
            Dictionary of secret validation results
        """
        required_secrets = [
            "JWT_SECRET_KEY",
            "POSTGRES_PASSWORD",
            "NEO4J_PASSWORD"
        ]

        results = {}
        for key in required_secrets:
            results[key] = self.get_secret(key) is not None

        return results


# Global secrets manager instance
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get global secrets manager instance"""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


# Convenience functions
def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get secret value"""
    return get_secrets_manager().get_secret(key, default)


def get_database_url(service: str) -> str:
    """Get database connection URL"""
    return get_secrets_manager().get_database_url(service)
