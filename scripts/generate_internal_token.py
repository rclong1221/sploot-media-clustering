#!/usr/bin/env python3
"""Generate a secure internal service token.

This script generates a cryptographically secure random token for
service-to-service authentication. The token should be:
1. Generated once during initial setup
2. Stored in environment variables or secrets management
3. Never committed to version control
4. Rotated periodically for security

Usage:
    python scripts/generate_internal_token.py

    # Save to environment file (do not commit!)
    python scripts/generate_internal_token.py >> .env.local

    # Produce raw token only (for automation)
    python scripts/generate_internal_token.py --raw

Most local developers should prefer the repository-level bootstrap helper:
    python scripts/bootstrap_internal_token.py  # run from repo root
"""
from __future__ import annotations

import argparse
import secrets
import string


def generate_internal_token(length: int = 64) -> str:
    """Generate a cryptographically secure random token.
    
    Args:
        length: Token length (default 64 characters)
        
    Returns:
        A URL-safe random token string
    """
    # Use URL-safe characters (alphanumeric + - and _)
    alphabet = string.ascii_letters + string.digits + '-_'
    token = ''.join(secrets.choice(alphabet) for _ in range(length))
    return token


def main() -> None:
    """Generate and print a new internal service token."""
    parser = argparse.ArgumentParser(description="Generate a secure internal service token.")
    parser.add_argument("--length", type=int, default=64, help="Token length (default: 64 characters)")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print only the token value (useful for automation/ scripting).",
    )

    args = parser.parse_args()

    token = generate_internal_token(length=args.length)

    if args.raw:
        print(token)
        return

    print("=" * 80)
    print("INTERNAL SERVICE TOKEN")
    print("=" * 80)
    print()
    print("Generated a new secure token for service-to-service authentication.")
    print()
    print("Add this to your environment configuration:")
    print()
    print(f"INTERNAL_SERVICE_TOKEN={token}")
    print()
    print("=" * 80)
    print("SECURITY NOTES:")
    print("=" * 80)
    print("1. Never commit this token to version control")
    print("2. Store in environment variables or secrets management")
    print("3. Use the same token across all internal services")
    print("4. Rotate periodically (e.g., every 90 days)")
    print("5. Revoke immediately if compromised")
    print()
    print("Services that need this token:")
    print("  - sploot_media_clustering (API server)")
    print("  - sploot-auth-service (client)")
    print()


if __name__ == "__main__":
    main()
