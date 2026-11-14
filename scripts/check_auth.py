"""Inspect the USA token response without printing credentials or token values.

Run locally with Home Assistant installed: python -m scripts.check_auth
This sends one password login request; it never sends vehicle commands.
"""

import getpass
import json

import requests

from custom_components.bluelink_api_hacs.bluelink_api import BluelinkAPI


def response_structure(value, depth=0):
    """Keep field names and types, replacing every response value."""
    if depth >= 6:
        return type(value).__name__
    if isinstance(value, dict):
        return {key: response_structure(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [response_structure(item, depth + 1) for item in value[:1]]
    return type(value).__name__


def main():
    username = input(
        "MyHyundai USA email (used locally, omitted from report): "
    ).strip()
    password = getpass.getpass("MyHyundai password (hidden): ")
    # The remote-command PIN is not needed for this authentication-only probe.
    api = BluelinkAPI(username, password, "")
    try:
        response = api._session.request(
            "POST",
            "https://api.telematics.hyundaiusa.com/v2/ac/oauth/token",
            timeout=30,
            headers=api._headers(),
            json={"username": username, "password": password},
        )
        summary = {"http_status": response.status_code}
        try:
            data = response.json()
        except ValueError:
            summary["response_structure"] = "Non-JSON response (body omitted)"
        else:
            summary["response_structure"] = response_structure(data)
            if isinstance(data, dict):
                summary["access_token_received"] = bool(data.get("access_token"))
                summary["mfa_challenge_received"] = bool(
                    data.get("password_token") or data.get("mfa_token")
                )
        print(json.dumps(summary, indent=2))
    except requests.RequestException as err:
        print(json.dumps({"connection_error_type": type(err).__name__}))
    finally:
        api.close()


if __name__ == "__main__":
    main()
