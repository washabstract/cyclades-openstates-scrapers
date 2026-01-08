# Open States Scrapers

This repository contains the code responsible for scraping bills & votes for Open States.
## Links

* [Contributor's Guide](https://docs.openstates.org/contributing/)
* [Documentation](https://docs.openstates.org/contributing/scrapers/)
* [Open States Issues](https://github.com/openstates/issues/issues)
* [Open States Discussions](https://github.com/openstates/issues/discussions)
* [Code of Conduct](https://docs.openstates.org/code-of-conduct/)


## Deploying a change

1. **Merge code into `main`**  
   Your changes land in the scraper repo.  

2. **CI Workflow builds and pushes to ECR**  
   GitHub Actions automatically builds the Docker image and publishes it to Amazon ECR (tagged with the commit SHA and `latest`).  

3. **PR opened in Artemis**  
   The workflow then opens a pull request in the [**Artemis repo**](https://github.com/washabstract/artemis). This PR updates the `.env` file with the new image tag.  

4. **Merge the Artemis PR**  
   Once approved, merging updates the DAG definitions to use the new image.  

5. **Deployment to Airflow**  
   Artemis syncs with MWAA, and the updated image tag rolls out automatically.  

6. **Validate & re-run**  
   Wait for the deployment to complete, then re-trigger the previously failed DAG [here](https://55bd462a-55fa-406a-ae6d-97b3240bb34c.c8.us-west-2.airflow.amazonaws.com/home).  


## Addressing Issues

Some problems will arise because we are out of sync with the main openstates branch, if you need just one commit, consider the following:

### Cherry-picking from Upstream

To bring in a specific commit from the upstream Open States repository:

```bash
# 1. Add upstream remote (if not already added)
git remote add upstream https://github.com/openstates/openstates-scrapers.git

# 2. Fetch the latest from upstream to get the commit
git fetch upstream

# 3. Cherry-pick the specific commit
git cherry-pick <commit-hash>

# 4. Push to your fork
git push origin <your-branch-name>
```

This preserves the original commit message and author while applying the changes to your current branch.


## Local Development (California Scraper)

To work with the California scraper locally, you can build and run the Dockerfile.california image.

1. **Build the CA image**

    Make sure you are in the project root and run the below. This mirrors the arguments used in CI so your local image matches what’s deployed.

```
docker build \
  -t cyclades-scrapers-ca:local \
  -f Dockerfile.california . \
  --platform linux/amd64 \
  --build-arg CACHE_BUCKET=$CACHE_BUCKET \
  --build-arg ELASTIC_CLOUD_ID=$ELASTIC_CLOUD_ID \
  --build-arg ELASTIC_BASIC_AUTH_USER=$ELASTIC_BASIC_AUTH_USER \
  --build-arg ELASTIC_BASIC_AUTH_PASS=$ELASTIC_BASIC_AUTH_PASS
```

2. **Enter the container**

```
docker run -it --rm \
  --platform linux/amd64 \
  -v $(pwd):/opt/openstates/openstates \
  cyclades-scrapers-ca:local \
  /bin/bash
```

3. **Run a test scrape**

    Inside the container, you can trigger the CA scraper manually. For example:

```
sed -i "s/user[[:space:]]*= mysql/user = root/" /etc/mysql/mariadb.conf.d/50-server.cnf && \
mysql_install_db --user=root && \
mkdir -p /run/mysqld && \
mysqld --user=root --max_allowed_packet=512M & \
sleep 5 && \
/opt/openstates/openstates/scrapers/ca/download.sh && \
poetry run os-update ca bills --fastmode --scrape
```
