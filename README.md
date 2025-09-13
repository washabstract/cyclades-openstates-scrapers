# Open States Scrapers

This repository contains the code responsible for scraping bills & votes for Open States.
## Links

* [Contributor's Guide](https://docs.openstates.org/contributing/)
* [Documentation](https://docs.openstates.org/contributing/scrapers/)
* [Open States Issues](https://github.com/openstates/issues/issues)
* [Open States Discussions](https://github.com/openstates/issues/discussions)
* [Code of Conduct](https://docs.openstates.org/code-of-conduct/)


## Deploying a change

1. Merge code to `main`
2. CI Workflow triggers - updates ECR Image
3. This opens a PR to Artemis (the airflow Repo)
4. Merge the Artemis PR
5. Artemis update the ECR Image tag
6. Wait for deploy
7. Trigger the failed DAG here: https://55bd462a-55fa-406a-ae6d-97b3240bb34c.c8.us-west-2.airflow.amazonaws.com/home


## Addressing Issues

Some problems will arise because we are out of sync with the main openstates branch, if you need just one commit, consider the following:

## Cherry-picking from Upstream

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
