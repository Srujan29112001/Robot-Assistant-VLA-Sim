"""
mTLS (Mutual TLS) Configuration
Secure communication between robot components
"""

import ssl
from pathlib import Path
from typing import Optional
import logging
import subprocess

logger = logging.getLogger(__name__)


def create_ssl_context(
    cert_file: str,
    key_file: str,
    ca_file: Optional[str] = None,
    verify_mode: int = ssl.CERT_REQUIRED,
) -> ssl.SSLContext:
    """
    Create SSL context for mTLS

    Args:
        cert_file: Path to certificate file
        key_file: Path to private key file
        ca_file: Path to CA certificate (for verification)
        verify_mode: SSL verification mode

    Returns:
        Configured SSL context
    """
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

    # Load server certificate and key
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)

    # Load CA for client verification (mutual TLS)
    if ca_file:
        context.load_verify_locations(cafile=ca_file)
        context.verify_mode = verify_mode

    # Use strong ciphers only
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')

    # Require TLS 1.2 or higher
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    logger.info("SSL context created for mTLS")
    return context


def generate_self_signed_cert(
    output_dir: str = "./certs",
    common_name: str = "robot-assistant",
    days_valid: int = 365,
) -> tuple:
    """
    Generate self-signed certificate for development/testing

    Args:
        output_dir: Directory to store certificates
        common_name: Common name for certificate
        days_valid: Number of days certificate is valid

    Returns:
        Tuple of (cert_path, key_path, ca_path)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cert_file = output_path / "server.crt"
    key_file = output_path / "server.key"
    ca_file = output_path / "ca.crt"

    # Generate CA certificate
    logger.info("Generating CA certificate...")
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:4096",
        "-keyout", str(output_path / "ca.key"),
        "-out", str(ca_file),
        "-days", str(days_valid),
        "-nodes",
        "-subj", f"/CN={common_name}-CA"
    ], check=True)

    # Generate server key
    logger.info("Generating server key...")
    subprocess.run([
        "openssl", "genrsa", "-out", str(key_file), "4096"
    ], check=True)

    # Generate certificate signing request
    logger.info("Generating CSR...")
    csr_file = output_path / "server.csr"
    subprocess.run([
        "openssl", "req", "-new",
        "-key", str(key_file),
        "-out", str(csr_file),
        "-subj", f"/CN={common_name}"
    ], check=True)

    # Sign certificate with CA
    logger.info("Signing certificate...")
    subprocess.run([
        "openssl", "x509", "-req",
        "-in", str(csr_file),
        "-CA", str(ca_file),
        "-CAkey", str(output_path / "ca.key"),
        "-CAcreateserial",
        "-out", str(cert_file),
        "-days", str(days_valid)
    ], check=True)

    logger.info(f"Certificates generated in {output_dir}")
    return str(cert_file), str(key_file), str(ca_file)


def setup_mtls(
    cert_dir: str = "./certs",
    generate_if_missing: bool = True,
) -> ssl.SSLContext:
    """
    Setup mTLS configuration

    Args:
        cert_dir: Directory containing certificates
        generate_if_missing: Generate self-signed certs if not found

    Returns:
        SSL context configured for mTLS
    """
    cert_path = Path(cert_dir)

    cert_file = cert_path / "server.crt"
    key_file = cert_path / "server.key"
    ca_file = cert_path / "ca.crt"

    # Check if certificates exist
    if not (cert_file.exists() and key_file.exists()):
        if generate_if_missing:
            logger.warning("Certificates not found, generating self-signed certificates...")
            cert_file, key_file, ca_file = generate_self_signed_cert(cert_dir)
        else:
            raise FileNotFoundError(f"Certificates not found in {cert_dir}")

    # Create SSL context
    context = create_ssl_context(
        cert_file=str(cert_file),
        key_file=str(key_file),
        ca_file=str(ca_file) if ca_file.exists() else None,
    )

    return context


# Usage with FastAPI/Uvicorn:
"""
from api.security.mtls import setup_mtls
import uvicorn

# Setup mTLS
ssl_context = setup_mtls()

# Run server with mTLS
uvicorn.run(
    "api.main:app",
    host="0.0.0.0",
    port=8443,
    ssl_certfile="./certs/server.crt",
    ssl_keyfile="./certs/server.key",
    ssl_ca_certs="./certs/ca.crt",
    ssl_cert_reqs=ssl.CERT_REQUIRED,  # Require client certificates
)
"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test certificate generation
    print("\n=== Generating Self-Signed Certificates ===")
    try:
        cert, key, ca = generate_self_signed_cert(
            output_dir="./test_certs",
            common_name="test-robot",
        )
        print(f"Generated:")
        print(f"  Certificate: {cert}")
        print(f"  Key: {key}")
        print(f"  CA: {ca}")

        # Test SSL context creation
        context = create_ssl_context(cert, key, ca)
        print(f"\nSSL Context created successfully")
        print(f"  Min TLS version: {context.minimum_version}")

    except Exception as e:
        logger.error(f"Failed to generate certificates: {e}")
        print("Note: OpenSSL must be installed for certificate generation")
