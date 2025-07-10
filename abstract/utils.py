import requests
from enum import Enum
import boto3
from kafka import KafkaProducer
import json
import logging

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
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    return producer

def init_local_kafka_producer() -> KafkaProducer:
    """
    Initialize a local Kafka producer for testing purposes.
    """
    return KafkaProducer(
        security_protocol="PLAINTEXT",
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def send_doc_to_kafka(doc_dict: dict, topic: str, kafka_producer: KafkaProducer = None):
    """
    Send a document dictionary to a Kafka topic.

    :param doc_dict: Dictionary containing document data.
    :param topic: Kafka topic to send the document to.
    """

    if not kafka_producer:
        kafka_producer = init_local_kafka_producer()

    kafka_producer.send(topic, doc_dict)


class SecretRetrievalError(Exception):
    def __init__(self, message, secret_name=None, original_exception=None):
        full_message = (
            f"{message}. Secret: {secret_name}. Details: {original_exception}"
            if original_exception
            else message
        )
        super().__init__(full_message)
        logging.error(full_message)
        self.secret_name = secret_name
        self.original_exception = original_exception


def get_secret(secret_name, region="us-west-2"):
    client = boto3.client(service_name="secretsmanager", region_name=region)
    try:
        secret_response = client.get_secret_value(SecretId=secret_name)
        secret_string = secret_response.get("SecretString")
        if not secret_string:
            raise SecretRetrievalError(
                "Secret is binary or unavailable in string format", secret_name
            )
        secret = json.loads(secret_string).get(secret_name)
        if not secret:
            raise SecretRetrievalError(
                "The key was not found in the secret", secret_name
            )
        return secret
    except Exception as e:
        raise SecretRetrievalError("Error retrieving secret", secret_name, e)