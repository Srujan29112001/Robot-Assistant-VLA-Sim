"""
ROS2 DDS Security Configuration
Implements ROS2 SROS2 (Secure ROS2) security features
"""

import os
from pathlib import Path
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def setup_ros2_security(
    keystore_path: str = "./ros2_security",
    create_keystore: bool = True,
) -> str:
    """
    Setup ROS2 DDS security (SROS2)

    Args:
        keystore_path: Path to security keystore
        create_keystore: Create keystore if it doesn't exist

    Returns:
        Path to keystore
    """
    keystore = Path(keystore_path)

    if not keystore.exists() and create_keystore:
        logger.info(f"Creating ROS2 security keystore at {keystore_path}")
        keystore.mkdir(parents=True, exist_ok=True)

        # Initialize keystore with ros2 security command
        try:
            subprocess.run([
                "ros2", "security", "create_keystore", str(keystore)
            ], check=True)
            logger.info("ROS2 security keystore created")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create keystore: {e}")
            logger.info("ROS2 security tools may not be installed")
        except FileNotFoundError:
            logger.warning("ros2 command not found - skipping keystore creation")

    # Set environment variables for ROS2 security
    os.environ["ROS_SECURITY_KEYSTORE"] = str(keystore.absolute())
    os.environ["ROS_SECURITY_ENABLE"] = "true"
    os.environ["ROS_SECURITY_STRATEGY"] = "Enforce"

    logger.info(f"ROS2 security enabled with keystore: {keystore_path}")
    return str(keystore.absolute())


def generate_security_artifacts(
    keystore_path: str,
    node_name: str,
    namespace: str = "/",
) -> bool:
    """
    Generate security artifacts for a ROS2 node

    Args:
        keystore_path: Path to security keystore
        node_name: Name of the node
        namespace: ROS2 namespace

    Returns:
        Success status
    """
    try:
        # Create security artifacts for the node
        subprocess.run([
            "ros2", "security", "create_key",
            keystore_path,
            namespace + node_name
        ], check=True)

        logger.info(f"Security artifacts created for node: {namespace}{node_name}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create security artifacts: {e}")
        return False
    except FileNotFoundError:
        logger.warning("ros2 security command not found")
        return False


def create_security_policy(
    keystore_path: str,
    node_name: str,
    allowed_topics: list,
    allowed_services: list,
) -> bool:
    """
    Create security policy for a node

    Args:
        keystore_path: Path to keystore
        node_name: Node name
        allowed_topics: List of allowed topic names
        allowed_services: List of allowed service names

    Returns:
        Success status
    """
    # In practice, this would create XML policy files
    # defining allowed topics, services, and actions for the node

    policy_dir = Path(keystore_path) / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)

    policy_file = policy_dir / f"{node_name}_policy.xml"

    # Create simple policy (simplified example)
    policy_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<policy version="0.2.0">
  <enclaves>
    <enclave path="/{node_name}">
      <profiles>
        <profile ns="/" node="{node_name}">
          <topics publish="ALLOW" subscribe="ALLOW">
"""

    for topic in allowed_topics:
        policy_content += f'            <topic>{topic}</topic>\n'

    policy_content += """          </topics>
          <services reply="ALLOW" request="ALLOW">
"""

    for service in allowed_services:
        policy_content += f'            <service>{service}</service>\n'

    policy_content += """          </services>
        </profile>
      </profiles>
    </enclave>
  </enclaves>
</policy>
"""

    policy_file.write_text(policy_content)
    logger.info(f"Security policy created: {policy_file}")

    return True


def configure_dds_security(
    domain_id: int = 0,
    governance_file: Optional[str] = None,
    permissions_file: Optional[str] = None,
) -> dict:
    """
    Configure DDS security settings

    Args:
        domain_id: ROS2 domain ID
        governance_file: Path to governance XML
        permissions_file: Path to permissions XML

    Returns:
        Dict of environment variables
    """
    env_vars = {
        "ROS_DOMAIN_ID": str(domain_id),
        "ROS_SECURITY_ENABLE": "true",
        "ROS_SECURITY_STRATEGY": "Enforce",
    }

    if governance_file:
        env_vars["ROS_SECURITY_GOVERNANCE_FILE"] = governance_file

    if permissions_file:
        env_vars["ROS_SECURITY_PERMISSIONS_FILE"] = permissions_file

    # Apply to current environment
    os.environ.update(env_vars)

    logger.info("DDS security configured")
    return env_vars


# Best practices documentation
SECURITY_BEST_PRACTICES = """
ROS2 Security Best Practices:

1. Enable SROS2 (Secure ROS2):
   - Create a security keystore
   - Generate keys for each node
   - Define access control policies

2. Use DDS Security:
   - Configure authentication
   - Enable encryption
   - Set access control lists

3. Network Segmentation:
   - Use VLANs or subnets
   - Firewall rules for ROS2 ports
   - Limit multicast traffic

4. Regular Updates:
   - Keep ROS2 and DDS updated
   - Monitor security advisories
   - Patch vulnerabilities promptly

5. Audit and Monitoring:
   - Log security events
   - Monitor unauthorized access
   - Regular security audits
"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== ROS2 Security Setup ===")

    # Setup security keystore
    keystore = setup_ros2_security(
        keystore_path="./test_ros2_security",
        create_keystore=True
    )

    print(f"Keystore path: {keystore}")
    print(f"ROS_SECURITY_ENABLE: {os.environ.get('ROS_SECURITY_ENABLE')}")

    # Generate artifacts for example node
    success = generate_security_artifacts(
        keystore_path=keystore,
        node_name="robot_controller",
        namespace="/"
    )

    print(f"Security artifacts generated: {success}")

    # Create security policy
    create_security_policy(
        keystore_path=keystore,
        node_name="robot_controller",
        allowed_topics=["/cmd_vel", "/scan", "/camera/image_raw"],
        allowed_services=["/navigate_to_pose", "/pick_object"]
    )

    print("\n" + SECURITY_BEST_PRACTICES)
