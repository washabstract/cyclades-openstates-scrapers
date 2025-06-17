from abstract.federal_agencies.federal_scraper import (
    scrape_federal_agency,
    write_out_scrape,
    init_kafka_producer,
)
from abstract.utils import (
    DocumentType,
    DEFAULT_FIELDS,
    send_doc_to_kafka,
)
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
    --extra-params '{"conditions[type]": "PRESDOCU", "conditions[presidential_document_type]": "executive_order"}'
    --kafka EO \
"""


def scrape_executive_orders(
    start_date: str = None, kafka_producer: str = "iris-kafka-cluster"):
    scrapes = scrape_federal_agency(
        fields=DEFAULT_FIELDS + EXTRA_FIELDS,
        start_date=start_date,
        extra_params=EXTRA_PARAMS,
    )

    if kafka_producer:
        producer = init_kafka_producer(kafka_producer)
        for doc in scrapes:
            send_doc_to_kafka(doc, topic="EO", kafka_producer=producer)
            print(f"Sent document {doc.get('executive_order_number')} to Kafka")
        producer.close()

    else:
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

    parser.add_argument(
        "--kafka",
        help="If set, will send the documents to Kafka at the given producer instead of writing them out (i.e '--kafka <topic>')",
        default=None,
    )

    args = parser.parse_args()

    scrape_executive_orders(
        start_date=args.start_date,
        kafka_producer=args.kafka if args.kafka else None,
    )
