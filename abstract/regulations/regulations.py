import os
import json
import time
import argparse
import requests
from datetime import datetime, timedelta
from abstract.utils import send_doc_to_kafka, init_kafka_producer, get_secret
from kafka import KafkaProducer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def save_json_locally(document_id, agency_id, content, out_dir="regulations"):
    folder = os.path.join(out_dir, agency_id)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, f"{document_id}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2)
    logger.info(f"Saved: {filepath}")

def fetch_documents(start_date, end_date, document_type, agency_id, api_key, kafka_cluster=None):
    BASE_URL = "https://api.regulations.gov/v4"

    doc_params = {
        "api_key": api_key,
        "filter[postedDate][ge]": start_date,
        "filter[postedDate][le]": end_date,
        "include": "attachments",
        "filter[agencyId]": agency_id,
        "filter[documentType]": document_type,
        "page[size]": 250
    }

    logger.info(f"Fetching documents from {start_date} to {end_date} for {agency_id}/{document_type}...")

    doc_resp = requests.get(f"{BASE_URL}/documents", params=doc_params)
    docs = doc_resp.json().get("data", [])
    logger.info(f"Found {len(docs)} documents")

    producer = None
    kafka_topic = agency_id.upper()

    if kafka_cluster == 'local':
        # Use direct KafkaProducer with host.docker.internal for local routing within Docker
        producer = KafkaProducer(
            bootstrap_servers="host.docker.internal:9092",
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            security_protocol="PLAINTEXT"
        )
        logger.info(f"Kafka enabled: topic '{kafka_topic}', local cluster on host.docker.internal:9092")
    elif kafka_cluster:
        producer = init_kafka_producer(kafka_cluster_name=kafka_cluster)
        logger.info(f"Kafka enabled: topic '{kafka_topic}', cluster '{kafka_cluster}'")

    try:
        for doc in docs:
            time.sleep(0.1) # Adding in a slight time delay to avoid overwhelming the regulations API
            doc_id = doc["id"]
            doc_response = requests.get(
                f"{BASE_URL}/documents/{doc_id}",
                params={"api_key": api_key, "include": "attachments"}
            )
            if doc_response.status_code == 200:
                doc_data = doc_response.json()
                agency = doc_data.get("data", {}).get("attributes", {}).get("agencyId", "UNKNOWN")

                if producer:
                    send_doc_to_kafka(doc_data, kafka_topic, kafka_producer=producer)
                    logger.info(f"Sent {doc_id} to Kafka topic '{kafka_topic}'")
                else:
                    save_json_locally(doc_id, agency, doc_data)
            else:
                logger.info(f"Failed to fetch {doc_id}: {doc_response.status_code}")
    finally:
        if producer:
            logger.info("Cleaning up Kafka producer")
            producer.flush()
            producer.close()
            logger.info(f"Finished sending to Kafka")

if __name__ == "__main__":
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    api_key = get_secret("REGULATIONS.GOV_API_KEY")

    parser = argparse.ArgumentParser(description="Regulations.gov scraper")
    parser.add_argument("--start-date", default=yesterday.isoformat(), help="Posted date start (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=today.isoformat(), help="Posted date end (YYYY-MM-DD)")
    parser.add_argument("--document-type", default="Proposed Rule", help="Document type (e.g. Proposed Rule)")
    parser.add_argument("--agency-id", required=True, help="Agency ID (e.g. DOT, EPA, TREAS)")
    parser.add_argument("--kafka-cluster", help="Kafka cluster name (MSK) or 'local' for local Kafka")

    args = parser.parse_args()

    fetch_documents(
        start_date=args.start_date,
        end_date=args.end_date,
        document_type=args.document_type,
        agency_id=args.agency_id,
        api_key=api_key,
        kafka_cluster=args.kafka_cluster
    )
