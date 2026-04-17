import requests
from config import BASE_URL_TEMPLATE


def get_base_url(data_center: str) -> str:
    return BASE_URL_TEMPLATE.format(dc=data_center)


def make_request(method: str, endpoint: str, api_token: str, body: dict = None) -> dict:
    """
    Unified API request handler for all Qualtrics API calls.

    Args:
        method:     HTTP method - 'GET', 'PUT', 'DELETE', 'POST'
        endpoint:   Full URL endpoint
        api_token:  Qualtrics API token
        body:       Optional request body (for PUT/POST)

    Returns:
        dict with keys: success (bool), status_code (int), data (dict), error (str)
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-API-TOKEN": api_token,
    }

    try:
        response = requests.request(
            method=method.upper(),
            url=endpoint,
            headers=headers,
            json=body,
            timeout=30,
        )

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        return {
            "success": response.ok,
            "status_code": response.status_code,
            "data": data,
            "error": None if response.ok else data.get("meta", {}).get("error", {}).get("errorMessage", response.text),
        }

    except requests.exceptions.ConnectionError:
        return {"success": False, "status_code": None, "data": {}, "error": "Connection error. Check your Data Center or network."}
    except requests.exceptions.Timeout:
        return {"success": False, "status_code": None, "data": {}, "error": "Request timed out."}
    except Exception as e:
        return {"success": False, "status_code": None, "data": {}, "error": str(e)}
