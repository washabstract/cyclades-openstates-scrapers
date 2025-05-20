import requests
from enum import Enum
DEFAULT_FIELDS = [
    "pdf_url",
    "agencies",
    "effective_on",
    "document_number",
    "title",
    "publication_date",
    "signing_date",
    "topics",
    "dates",
    "raw_text_url",
]

class DocumentType(Enum):
    RULE = "RULE"
    PRORULE = "PRORULE"
    NOTICE = "NOTICE"
    PRESDOCU = "PRESDOCU"


def federal_scrape(
    fields: dict = DEFAULT_FIELDS,
    exact_date: str = None,
    start_date: str = None,
    extra_params: dict = None,
):
    """
    Fetch executive orders from the Federal Register API. By default, scrapes all available orders from 1994 onwards.
    exact_date or start_date are optional, though mutually exclusive. If both are provided, only exact_date will be used.

    :param fields: List of fields to include in the response.
    :param exact_date: Fetch orders from a specific date (YYYY-MM-DD).
    :param start_date: Fetch orders from this date onwards (YYYY-MM-DD).
    :return: List of executive orders.
    """
    base_url = "https://www.federalregister.gov/api/v1/documents.json"

    params = {
        "order": "oldest",
        "per_page": 1000,
    }

    if exact_date:
        params["conditions[publication_date][is]"] = exact_date
    elif start_date:  # elif since start_date and exact_date are mutually exclusive
        params["conditions[publication_date][gte]"] = start_date

    if extra_params:
        for key, value in extra_params.items():
            params[key] = value

    if fields:
        params["fields[]"] = fields

    return get_all_documents_recurse(base_url, params)


def get_all_documents_recurse(url, params):
    response = requests.get(url, params)

    if response.status_code == 200:
        data = response.json()
        results = (
            [] if not data.get("count", 0) else data["results"]
        )  # Sometimes, there's another page indicated but nothing on it (no results field)

        if "next_page_url" in data:
            results.extend(get_all_documents_recurse(data["next_page_url"], params))

        return results

    else:
        print(f"Error: {response.json()}")
        return []

