from federal_scraper import (
    federal_scrape,
    write_out_scrape,
)
from federal_utils import DocumentType, DEFAULT_FIELDS
import argparse

EXTRA_FIELDS = ["executive_order_number", "presidential_document_number"]
EXTRA_PARAMS = {
    "conditions[type]": DocumentType.PRESDOCU.value,
    "conditions[presidential_document_type]": "executive_order",
}
DOCUMENT_HEADER = "executive_order_number"
OUTPUT_DIR = "executive_orders"

command = """
python agencies/federal_scraper.py \
    --extra-fields executive_order_number,presidential_document_number \
    --document-title executive_order_number
    --extra-params '{"conditions[type]": "PRESDOCU", "conditions[presidential_document_type]": "executive_order"}' \
"""


def scrape_executive_orders(start_date: str = None):
    scrapes = federal_scrape(
        fields=DEFAULT_FIELDS + EXTRA_FIELDS,
        start_date=start_date,
        extra_params=EXTRA_PARAMS,
    )

    write_out_scrape(
        scraped_jsons=scrapes,
        output_dir=OUTPUT_DIR,
        document_title=DOCUMENT_HEADER,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch executive orders from the Federal Register API."
    )
    parser.add_argument(
        "--start-date", help="Fetch orders from a specific date (YYYY-MM-DD)"
    )

    args = parser.parse_args()

    scrape_executive_orders(
        start_date=args.start_date,
    )
