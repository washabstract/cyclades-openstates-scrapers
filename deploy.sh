#!/bin/sh

DOCKER_IMAGE=254491760475.dkr.ecr.us-west-2.amazonaws.com/cyclades-scrapers:latest
DOCKER_TAG=cyclades-scrapers:latest
DOCKER_IMAGE_NAME=cyclades-scrapers

AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY

echo "Building and deploying to AWS. Confirm? (y/n) " 
read confirmation

if [ $confirmation = "y" ]
then
    echo "Confirmed, building and deploying"
    docker build -f Dockerfile -t $DOCKER_IMAGE_NAME . --platform linux/amd64 --build-arg AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID --build-arg AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
    aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin 254491760475.dkr.ecr.us-west-2.amazonaws.com    
    docker tag $DOCKER_TAG $DOCKER_IMAGE
    docker push $DOCKER_IMAGE
fi