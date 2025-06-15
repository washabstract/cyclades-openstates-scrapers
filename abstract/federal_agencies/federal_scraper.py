from federal_utils import (
    scrape_federal_agency,
    DEFAULT_FIELDS,
    send_doc_to_kafka,
    init_kafka_producer,
)
import os
import sys
import json
import argparse


def write_out_scrape(
    scraped_jsons: list[dict],
    output_dir: str = "fed_scrapes",
    full: bool = False,
    document_title: str = "document_number",
):
    """
    Write out the scrape to a file.
    :param jsons: List of JSON objects to write out.
    :param output_dir: Directory to write out the files to.
    :param full: If True, write out a single file with all the JSON objects.
    """
    # make directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory {output_dir}", file=sys.stderr)

    if full:
        with open(f"{output_dir}/full_scrape.json", "w") as f:
            f.write(json.dumps(scraped_jsons, indent=2))
            print(
                f"Wrote {len(scraped_jsons)} orders to full_scrape.json",
                file=sys.stderr,
            )
    else:
        for file in scraped_jsons:
            document_title_value = file.get(document_title, file.get("document_number", "unknown"))
            with open(f"{output_dir}/{document_title_value}.json", "w") as f:
                f.write(json.dumps(file, indent=2))
        print(f"Wrote {len(scraped_jsons)} orders to individual files", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch federal documents from the Federal Register API."
    )
    parser.add_argument(
        "--exact-date", help="Fetch orders from a specific date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--start-date", help="Fetch orders from this date onwards (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--group",
        help="Defaults to False, if True, will group all orders into a single file",
        action="store_true",
    )

    parser.add_argument(
        "--fields",
        help="Comma-separated list of fields to include in the response",
        default=",".join(DEFAULT_FIELDS),
    )

    parser.add_argument(
        "--extra-fields",
        help="Comma-separated list of extra fields to include in the response",
        default="",
    )
    parser.add_argument(
        "--extra-params",
        help="json string of extra parameters to include in the request",
        default="{}",
    )

    parser.add_argument(
        "--document-title",
        help="Which field to use for the document title",
        default="document_number",
    )

    parser.add_argument(
        "--kafka",
        help="If set, will send the documents to Kafka at the given topic instead of writing them out (i.e '--kafka <topic>')",
        default=None
    )

    parser.add_argument(
        "--output-dir", help="Directory to save the output files", default="fed_scrapes"
    )

    args = parser.parse_args()

    extra_params = {**json.loads(args.extra_params)}
    fields = args.fields.split(",") + args.extra_fields.split(",")
    print(f"Extra params: {extra_params}", file=sys.stderr)
    print(f"Fields: {fields}", file=sys.stderr)

    scraped_documents = scrape_federal_agency(
        fields=args.fields.split(",") + args.extra_fields.split(","),
        exact_date=args.exact_date,
        start_date=args.start_date,
        extra_params=extra_params,
    )

    if args.kafka:
        kakfa_producer = init_kafka_producer(args.kafka)
        for doc in scraped_documents:
            send_doc_to_kafka(doc, topic=args.kafka, kakfa_producer=kakfa_producer)
            print(f"Sent document {doc.get(args.document_title)} to Kafka")
        return
    
    else:
        write_out_scrape(
            scraped_documents, args.output_dir, args.group, args.document_title
        )


if __name__ == "__main__":
    main()
