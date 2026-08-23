#!/bin/sh
# Idempotent SeaweedFS S3 initialisation.
# Creates buckets and configures access credentials via weed shell.
# Safe to re-run: bucket creation commands are no-ops if the bucket already exists.
#
# Usage (from repo root):
#   docker compose exec -T seaweedfs-master sh /scripts/init.sh
#
# The master flag points at the local master process running inside the container.
MASTER="localhost:9333"

echo "s3.bucket.create -name raw-flights"       | weed shell -master="${MASTER}"
echo "s3.bucket.create -name frontend-exports"  | weed shell -master="${MASTER}"
echo "s3.bucket.create -name bts-raw"           | weed shell -master="${MASTER}"
echo "s3.configure -user=admin -access_key=admin -secret_key=admin -actions=Read,Write,List,Tagging,Admin -apply" \
    | weed shell -master="${MASTER}"
echo "s3.configure -user=anonymous -buckets=frontend-exports -actions=Read,List -apply" \
    | weed shell -master="${MASTER}"

echo "SeaweedFS S3 initialisation complete."
