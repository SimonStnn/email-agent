#!/usr/bin/env python3
"""
Authenticate Microsoft accounts for use with M365 MCP.
Run this script to sign in to one or more Microsoft accounts.
"""

import os
import sys
import argparse
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv


def _parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Authenticate Microsoft accounts for M365 MCP"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env file (default: .env)",
    )
    return parser.parse_args()


def main():
    # Parse arguments first to get env file path
    args = _parse_arguments()

    # Load environment variables from custom path
    env_file = args.env_file
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
        print(f"Loaded environment from: {env_file}\n")
    else:
        print(f"Warning: Environment file not found: {env_file}")
        print("Continuing with system environment variables...\n")

    # Import auth module after loading environment
    from m365_mcp import auth

    if not os.getenv("M365_MCP_CLIENT_ID"):
        print("Error: M365_MCP_CLIENT_ID environment variable is required")
        print("\nPlease set it in your .env file or environment:")
        print("export M365_MCP_CLIENT_ID='your-app-id'")
        sys.exit(1)

    print("M365 MCP Authentication")
    print("============================\n")

    # List current accounts
    accounts = auth.list_accounts()
    if accounts:
        print("Currently authenticated accounts:")
        for i, account in enumerate(accounts, 1):
            print(f"{i}. {account.username} (ID: {account.account_id})")
        print()
    else:
        print("No accounts currently authenticated.\n")

    # Authenticate new account
    while True:
        choice = input("Do you want to authenticate a new account? (y/n): ").lower()
        if choice == "n":
            break
        elif choice == "y":
            try:
                # Use the new authentication function
                new_account = auth.authenticate_new_account()

                if new_account:
                    print("\n✓ Authentication successful!")
                    print(f"Signed in as: {new_account.username}")
                    print(f"Account ID: {new_account.account_id}")
                else:
                    print(
                        "\n✗ Authentication failed: Could not retrieve account information"
                    )
            except Exception as e:
                print(f"\n✗ Authentication failed: {e}")
                continue

            print()
        else:
            print("Please enter 'y' or 'n'")

    # Final account summary
    accounts = auth.list_accounts()
    if accounts:
        print("\nAuthenticated accounts summary:")
        print("==============================")
        for account in accounts:
            print(f"• {account.username}")
            print(f"  Account ID: {account.account_id}")

        print(
            "\nYou can use these account IDs with any MCP tool by passing account_id parameter."
        )
        print("Example: send_email(..., account_id='<account-id>')")
    else:
        print("\nNo accounts authenticated.")

    print("\nAuthentication complete!")


if __name__ == "__main__":
    main()
