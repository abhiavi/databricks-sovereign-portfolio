import base64
import time
import jwt
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

class JWTValidator:
    """
    Asymmetric RS256 JWT Validator for On-Behalf-Of (OBO) token verification,
    mimicking Databricks Unity Catalog OIDC authentication.
    """
    def __init__(self, key_id: str = "mock-unity-catalog-key-id-2026"):
        self.key_id = key_id
        # Generate asymmetric RSA key pair on startup
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        self.public_key = self.private_key.public_key()
        
    def get_jwks(self) -> Dict[str, Any]:
        """
        Formats the public key as a standard JSON Web Key Set (JWKS).
        """
        numbers = self.public_key.public_key_numbers()
        
        # Convert integer to Base64URL encoding
        def int_to_b64url(val: int) -> str:
            val_bytes = val.to_bytes((val.bit_length() + 7) // 8, byteorder='big')
            return base64.urlsafe_b64encode(val_bytes).decode('utf-8').rstrip('=')
            
        n_b64 = int_to_b64url(numbers.n)
        e_b64 = int_to_b64url(numbers.e)
        
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "alg": "RS256",
                    "use": "sig",
                    "kid": self.key_id,
                    "n": n_b64,
                    "e": e_b64
                }
            ]
        }

    def generate_mock_token(self, payload_override: Optional[Dict[str, Any]] = None) -> str:
        """
        Generates a valid RS256 signed mock JWT token for validation testing.
        """
        now = int(time.time())
        default_payload = {
            "iss": "https://databricks-sovereign-fleet.com",
            "aud": "natoma-mcp-proxy-2026",
            "sub": "user_abhishek",
            "exp": now + 3600,
            "iat": now,
            "nbf": now,
            # Custom metadata containment mapping claim
            "metadata_containment": {
                "allowed_catalogs": ["prod_finance", "dev_sandbox"],
                "allowed_actions": ["SELECT_ONLY", "DESCRIBE_ONLY"]
            }
        }
        
        payload = {**default_payload, **(payload_override or {})}
        
        # Sign the token using the private key
        pem_private = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        headers = {"kid": self.key_id}
        
        return jwt.encode(payload, pem_private, algorithm="RS256", headers=headers)

    def decode_and_verify(self, token: str) -> Dict[str, Any]:
        """
        Decodes the token, verifies the asymmetric signature using the public key,
        and enforces standard claims validation.
        """
        pem_public = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Decode and verify using PyJWT
        # Expect audience: 'natoma-mcp-proxy-2026' and issuer: 'https://databricks-sovereign-fleet.com'
        claims = jwt.decode(
            token,
            pem_public,
            algorithms=["RS256"],
            audience="natoma-mcp-proxy-2026",
            issuer="https://databricks-sovereign-fleet.com",
            options={"require": ["exp", "iss", "aud", "metadata_containment"]}
        )
        
        return claims
