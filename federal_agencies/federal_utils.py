import requests
from enum import Enum
import boto3
from kafka import KafkaProducer
import json
import os

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


def scrape_federal_agency(
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


def init_kafka_producer(kafka_cluster_name: str) -> KafkaProducer:
    client = boto3.client("kafka", region_name="us-west-2")

    # Grab Cluster Arn
    clusters = client.list_clusters()["ClusterInfoList"]
    cluster_arn = None
    for cluster in clusters:
        if cluster["ClusterName"] == kafka_cluster_name:
            cluster_arn = cluster["ClusterArn"]
            break

    if cluster_arn is None:
        raise ValueError(f"No Kafka cluster found with name: {kafka_cluster_name}")

    # Grab Brokers
    response = client.get_bootstrap_brokers(ClusterArn=cluster_arn)
    kafka_brokers = response["BootstrapBrokerStringTls"]

    producer = KafkaProducer(
        security_protocol="SSL",
        bootstrap_servers=kafka_brokers,
        value_serializer=lambda v: json.dumps(v, json.dumps(v).encode("utf-8")),
    )

    return producer


def send_doc_to_kafka(doc_dict: dict, topic: str, kafka_producer: KafkaProducer = None):
    """
    Send a document dictionary to a Kafka topic.

    :param doc_dict: Dictionary containing document data.
    :param topic: Kafka topic to send the document to.
    """

    if not kafka_producer:
        kafka_producer = KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

    kafka_producer.send(topic, doc_dict)
    kafka_producer.flush()
    kafka_producer.close()
