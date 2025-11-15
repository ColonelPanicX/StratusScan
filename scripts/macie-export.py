#!/usr/bin/env python3
"""
AWS Macie Export Script for StratusScan

Exports comprehensive AWS Macie data security and privacy information including
classification jobs, sensitive data findings, S3 bucket inventory, and custom data identifiers.

Features:
- Macie Status: Account-level Macie configuration and status
- Classification Jobs: Sensitive data discovery jobs
- Findings: Sensitive data and policy violations
- S3 Buckets: Bucket inventory with sensitivity scores
- Custom Data Identifiers: Custom regex patterns for data classification
- Summary: Job counts, finding statistics, and metrics

Output: Excel file with 6 worksheets
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    import utils
except ImportError:
    script_dir = Path(__file__).parent.absolute()
    if script_dir.name.lower() == 'scripts':
        sys.path.append(str(script_dir.parent))
    else:
        sys.path.append(str(script_dir))
    import utils

try:
    import pandas as pd
except ImportError:
    utils.log_error("pandas library is required but not installed")
    utils.log_error("Install with: pip install pandas")
    sys.exit(1)


@utils.aws_error_handler("Collecting Macie status", default_return=[])
def collect_macie_status(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect Macie account status from AWS regions."""
    all_status = []

    for region in regions:
        utils.log_info(f"Checking Macie status in {region}...")
        macie_client = utils.get_boto3_client('macie2', region_name=region)

        try:
            # Get Macie status
            status_response = macie_client.get_macie_session()

            status = status_response.get('status', 'N/A')
            finding_publishing_frequency = status_response.get('findingPublishingFrequency', 'N/A')
            service_role = status_response.get('serviceRole', 'N/A')

            # Extract role name
            role_name = 'N/A'
            if service_role != 'N/A' and '/' in service_role:
                role_name = service_role.split('/')[-1]

            # Created and updated timestamps
            created_at = status_response.get('createdAt')
            if created_at:
                created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                created_at_str = 'N/A'

            updated_at = status_response.get('updatedAt')
            if updated_at:
                updated_at_str = updated_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                updated_at_str = 'N/A'

            all_status.append({
                'Region': region,
                'Status': status,
                'Finding Publishing Frequency': finding_publishing_frequency,
                'Service Role': role_name,
                'Created': created_at_str,
                'Updated': updated_at_str,
            })

        except Exception as e:
            # Macie might not be enabled in this region
            utils.log_warning(f"Macie not enabled or error in {region}: {str(e)}")
            all_status.append({
                'Region': region,
                'Status': 'Not Enabled',
                'Finding Publishing Frequency': 'N/A',
                'Service Role': 'N/A',
                'Created': 'N/A',
                'Updated': 'N/A',
            })

    return all_status


@utils.aws_error_handler("Collecting Macie classification jobs", default_return=[])
def collect_classification_jobs(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect Macie classification job information from AWS regions."""
    all_jobs = []

    for region in regions:
        utils.log_info(f"Scanning Macie classification jobs in {region}...")
        macie_client = utils.get_boto3_client('macie2', region_name=region)

        try:
            paginator = macie_client.get_paginator('list_classification_jobs')
            for page in paginator.paginate():
                job_summaries = page.get('items', [])

                for job_summary in job_summaries:
                    job_id = job_summary.get('jobId', 'N/A')
                    job_name = job_summary.get('name', 'N/A')
                    job_type = job_summary.get('jobType', 'N/A')
                    job_status = job_summary.get('jobStatus', 'N/A')

                    # Get detailed job information
                    try:
                        job_response = macie_client.describe_classification_job(jobId=job_id)

                        # Bucket definitions
                        s3_job_definition = job_response.get('s3JobDefinition', {})
                        bucket_definitions = s3_job_definition.get('bucketDefinitions', [])
                        bucket_names = [bd.get('accountId', '') + '/' + bd.get('buckets', [''])[0]
                                       for bd in bucket_definitions if bd.get('buckets')]
                        buckets_str = ', '.join(bucket_names[:3]) if bucket_names else 'N/A'
                        if len(bucket_names) > 3:
                            buckets_str += f' (+{len(bucket_names) - 3} more)'

                        # Schedule
                        schedule_frequency = job_response.get('scheduleFrequency', {})
                        schedule_type = 'One-time' if job_type == 'ONE_TIME' else schedule_frequency.get('weeklySchedule', 'N/A')

                        # Statistics
                        statistics = job_response.get('statistics', {})
                        approximate_objects_to_process = statistics.get('approximateNumberOfObjectsToProcess', 0)
                        objects_processed = statistics.get('numberOfRuns', 0)

                        # Timestamps
                        created_at = job_response.get('createdAt')
                        if created_at:
                            created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            created_at_str = 'N/A'

                        last_run_time = job_response.get('lastRunTime')
                        if last_run_time:
                            last_run_time_str = last_run_time.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            last_run_time_str = 'Never'

                        all_jobs.append({
                            'Region': region,
                            'Job Name': job_name,
                            'Job ID': job_id,
                            'Type': job_type,
                            'Status': job_status,
                            'Schedule': schedule_type,
                            'Buckets': buckets_str,
                            'Objects to Process': approximate_objects_to_process,
                            'Runs': objects_processed,
                            'Created': created_at_str,
                            'Last Run': last_run_time_str,
                        })

                    except Exception as e:
                        utils.log_warning(f"Could not get details for job {job_name}: {str(e)}")
                        continue

        except Exception as e:
            utils.log_warning(f"Could not list Macie classification jobs in {region}: {str(e)}")

        utils.log_success(f"Collected {len([j for j in all_jobs if j['Region'] == region])} Macie classification jobs from {region}")

    return all_jobs


@utils.aws_error_handler("Collecting Macie findings", default_return=[])
def collect_findings(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect Macie finding information from AWS regions (recent findings only)."""
    all_findings = []

    for region in regions:
        utils.log_info(f"Scanning Macie findings in {region}...")
        macie_client = utils.get_boto3_client('macie2', region_name=region)

        try:
            # List findings (limit to most recent)
            findings_response = macie_client.list_findings(maxResults=50)
            finding_ids = findings_response.get('findingIds', [])

            if finding_ids:
                # Get finding details
                findings_details = macie_client.get_findings(findingIds=finding_ids)
                findings = findings_details.get('findings', [])

                for finding in findings:
                    finding_id = finding.get('id', 'N/A')
                    finding_type = finding.get('type', 'N/A')
                    severity = finding.get('severity', {}).get('description', 'N/A')

                    # S3 resource
                    resources = finding.get('resourcesAffected', {})
                    s3_bucket = resources.get('s3Bucket', {})
                    bucket_name = s3_bucket.get('name', 'N/A')

                    s3_object = resources.get('s3Object', {})
                    object_key = s3_object.get('key', 'N/A')

                    # Category
                    category = finding.get('category', 'N/A')

                    # Count (for sensitive data findings)
                    count = finding.get('count', 1)

                    # Timestamps
                    created_at = finding.get('createdAt')
                    if created_at:
                        created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        created_at_str = 'N/A'

                    updated_at = finding.get('updatedAt')
                    if updated_at:
                        updated_at_str = updated_at.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        updated_at_str = 'N/A'

                    # Description
                    description = finding.get('description', 'N/A')

                    all_findings.append({
                        'Region': region,
                        'Finding ID': finding_id,
                        'Type': finding_type,
                        'Severity': severity,
                        'Category': category,
                        'Bucket': bucket_name,
                        'Object Key': object_key,
                        'Count': count,
                        'Description': description,
                        'Created': created_at_str,
                        'Updated': updated_at_str,
                    })

        except Exception as e:
            utils.log_warning(f"Could not list Macie findings in {region}: {str(e)}")

        utils.log_success(f"Collected {len([f for f in all_findings if f['Region'] == region])} Macie findings from {region}")

    return all_findings


@utils.aws_error_handler("Collecting Macie S3 buckets", default_return=[])
def collect_s3_buckets(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect Macie S3 bucket inventory from AWS regions."""
    all_buckets = []

    for region in regions:
        utils.log_info(f"Scanning Macie S3 bucket inventory in {region}...")
        macie_client = utils.get_boto3_client('macie2', region_name=region)

        try:
            paginator = macie_client.get_paginator('describe_buckets')
            for page in paginator.paginate():
                buckets = page.get('buckets', [])

                for bucket in buckets:
                    bucket_name = bucket.get('bucketName', 'N/A')
                    account_id = bucket.get('accountId', 'N/A')

                    # Public access
                    public_access = bucket.get('publicAccess', {})
                    effective_permission = public_access.get('effectivePermission', 'N/A')

                    # Encryption
                    server_side_encryption = bucket.get('serverSideEncryption', {})
                    encryption_type = server_side_encryption.get('type', 'N/A')

                    # Object count and size
                    object_count = bucket.get('objectCount', 0)
                    size_in_bytes = bucket.get('sizeInBytes', 0)
                    size_in_gb = round(size_in_bytes / (1024**3), 2) if size_in_bytes else 0

                    # Classifiable objects
                    classifiable_object_count = bucket.get('classifiableObjectCount', 0)
                    classifiable_size_in_bytes = bucket.get('classifiableSizeInBytes', 0)

                    # Shared access
                    shared_access = bucket.get('sharedAccess', 'N/A')

                    # Job details
                    job_details = bucket.get('jobDetails', {})
                    last_job_id = job_details.get('lastJobId', 'N/A') if job_details else 'N/A'

                    all_buckets.append({
                        'Region': region,
                        'Bucket Name': bucket_name,
                        'Account ID': account_id,
                        'Public Access': effective_permission,
                        'Shared Access': shared_access,
                        'Encryption': encryption_type,
                        'Object Count': object_count,
                        'Size (GB)': size_in_gb,
                        'Classifiable Objects': classifiable_object_count,
                        'Last Job ID': last_job_id,
                    })

        except Exception as e:
            utils.log_warning(f"Could not describe S3 buckets in Macie for {region}: {str(e)}")

        utils.log_success(f"Collected {len([b for b in all_buckets if b['Region'] == region])} S3 buckets from Macie in {region}")

    return all_buckets


@utils.aws_error_handler("Collecting Macie custom data identifiers", default_return=[])
def collect_custom_data_identifiers(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect Macie custom data identifier information from AWS regions."""
    all_identifiers = []

    for region in regions:
        utils.log_info(f"Scanning Macie custom data identifiers in {region}...")
        macie_client = utils.get_boto3_client('macie2', region_name=region)

        try:
            paginator = macie_client.get_paginator('list_custom_data_identifiers')
            for page in paginator.paginate():
                identifier_summaries = page.get('items', [])

                for identifier in identifier_summaries:
                    identifier_id = identifier.get('id', 'N/A')
                    name = identifier.get('name', 'N/A')
                    description = identifier.get('description', 'N/A')

                    # Get detailed information
                    try:
                        details_response = macie_client.get_custom_data_identifier(id=identifier_id)

                        regex = details_response.get('regex', 'N/A')
                        keywords = details_response.get('keywords', [])
                        keywords_str = ', '.join(keywords[:5]) if keywords else 'None'
                        if len(keywords) > 5:
                            keywords_str += f' (+{len(keywords) - 5} more)'

                        ignore_words = details_response.get('ignoreWords', [])
                        ignore_words_str = ', '.join(ignore_words[:5]) if ignore_words else 'None'

                        maximum_match_distance = details_response.get('maximumMatchDistance', 'N/A')

                        # Timestamps
                        created_at = details_response.get('createdAt')
                        if created_at:
                            created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            created_at_str = 'N/A'

                        all_identifiers.append({
                            'Region': region,
                            'Name': name,
                            'ID': identifier_id,
                            'Regex Pattern': regex,
                            'Keywords': keywords_str,
                            'Ignore Words': ignore_words_str,
                            'Max Match Distance': maximum_match_distance,
                            'Description': description,
                            'Created': created_at_str,
                        })

                    except Exception as e:
                        utils.log_warning(f"Could not get details for identifier {name}: {str(e)}")
                        continue

        except Exception as e:
            utils.log_warning(f"Could not list custom data identifiers in {region}: {str(e)}")

        utils.log_success(f"Collected {len([i for i in all_identifiers if i['Region'] == region])} custom data identifiers from {region}")

    return all_identifiers


def generate_summary(status: List[Dict[str, Any]],
                     jobs: List[Dict[str, Any]],
                     findings: List[Dict[str, Any]],
                     buckets: List[Dict[str, Any]],
                     identifiers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate summary statistics for Macie resources."""
    summary = []

    # Macie enabled regions
    enabled_regions = len([s for s in status if s['Status'] != 'Not Enabled'])
    summary.append({
        'Metric': 'Macie Enabled Regions',
        'Count': enabled_regions,
        'Details': f"{enabled_regions}/{len(status)} regions with Macie enabled"
    })

    summary.append({
        'Metric': 'Total Classification Jobs',
        'Count': len(jobs),
        'Details': f"{len([j for j in jobs if j['Status'] == 'RUNNING'])} running, {len([j for j in jobs if j['Status'] == 'COMPLETE'])} complete"
    })

    summary.append({
        'Metric': 'Total Findings (Recent)',
        'Count': len(findings),
        'Details': f"Last 50 findings per region"
    })

    summary.append({
        'Metric': 'Total S3 Buckets Monitored',
        'Count': len(buckets),
        'Details': f"{len(buckets)} buckets in Macie inventory"
    })

    summary.append({
        'Metric': 'Custom Data Identifiers',
        'Count': len(identifiers),
        'Details': f"{len(identifiers)} custom regex patterns"
    })

    # Finding severity distribution
    if findings:
        severities = {}
        for finding in findings:
            severity = finding['Severity']
            severities[severity] = severities.get(severity, 0) + 1

        severity_details = ', '.join([f"{sev}: {count}" for sev, count in sorted(severities.items())])
        summary.append({
            'Metric': 'Finding Severity Distribution',
            'Count': len(severities),
            'Details': severity_details
        })

    # Public access buckets
    if buckets:
        public_buckets = len([b for b in buckets if b['Public Access'] in ['PUBLIC', 'UNKNOWN']])
        summary.append({
            'Metric': '⚠️ Publicly Accessible Buckets',
            'Count': public_buckets,
            'Details': f"{public_buckets} buckets with public access"
        })

    # Total data monitored
    if buckets:
        total_size_gb = sum(b['Size (GB)'] for b in buckets if isinstance(b['Size (GB)'], (int, float)))
        summary.append({
            'Metric': 'Total Data Monitored',
            'Count': round(total_size_gb, 2),
            'Details': f"{round(total_size_gb, 2)} GB across all buckets"
        })

    return summary


def main():
    """Main execution function."""
    script_name = Path(__file__).stem
    utils.setup_logging(script_name)
    utils.log_script_start(script_name)

    # Check dependencies
    if not utils.check_dependencies(['pandas', 'openpyxl', 'boto3']):
        utils.log_error("Required dependencies not installed")
        return

    # Get account information
    account_id, account_name = utils.get_account_info()
    utils.log_info(f"Account: {account_name} ({account_id})")

    # Region selection
    print("\n=== Region Selection ===")
    print("1. All regions")
    print("2. Specific region")
    region_choice = input("Enter your choice (1-2): ").strip()

    if region_choice == '1':
        # Get all AWS regions
        regions = utils.get_all_aws_regions('macie2')
        utils.log_info(f"Scanning all {len(regions)} AWS regions")
    elif region_choice == '2':
        region = input("Enter AWS region (e.g., us-east-1): ").strip()
        if not utils.validate_aws_region(region):
            utils.log_error(f"Invalid AWS region: {region}")
            return
        regions = [region]
        utils.log_info(f"Scanning region: {region}")
    else:
        utils.log_error("Invalid choice")
        return

    # Collect data
    print("\n=== Collecting Macie Data ===")
    status = collect_macie_status(regions)
    jobs = collect_classification_jobs(regions)
    findings = collect_findings(regions)
    buckets = collect_s3_buckets(regions)
    identifiers = collect_custom_data_identifiers(regions)

    # Generate summary
    summary = generate_summary(status, jobs, findings, buckets, identifiers)

    # Convert to DataFrames
    status_df = pd.DataFrame(status) if status else pd.DataFrame()
    jobs_df = pd.DataFrame(jobs) if jobs else pd.DataFrame()
    findings_df = pd.DataFrame(findings) if findings else pd.DataFrame()
    buckets_df = pd.DataFrame(buckets) if buckets else pd.DataFrame()
    identifiers_df = pd.DataFrame(identifiers) if identifiers else pd.DataFrame()
    summary_df = pd.DataFrame(summary)

    # Prepare DataFrames for export
    if not status_df.empty:
        status_df = utils.prepare_dataframe_for_export(status_df)
    if not jobs_df.empty:
        jobs_df = utils.prepare_dataframe_for_export(jobs_df)
    if not findings_df.empty:
        findings_df = utils.prepare_dataframe_for_export(findings_df)
    if not buckets_df.empty:
        buckets_df = utils.prepare_dataframe_for_export(buckets_df)
    if not identifiers_df.empty:
        identifiers_df = utils.prepare_dataframe_for_export(identifiers_df)
    if not summary_df.empty:
        summary_df = utils.prepare_dataframe_for_export(summary_df)

    # Create export filename
    region_suffix = regions[0] if len(regions) == 1 else 'all-regions'
    filename = utils.create_export_filename(account_name, 'macie', region_suffix)

    # Save to Excel with multiple sheets
    print("\n=== Exporting to Excel ===")
    dataframes = {
        'Macie Status': status_df,
        'Classification Jobs': jobs_df,
        'Findings': findings_df,
        'S3 Buckets': buckets_df,
        'Custom Data Identifiers': identifiers_df,
        'Summary': summary_df
    }

    if utils.save_multiple_dataframes_to_excel(dataframes, filename):
        utils.log_export_summary(
            filename=filename,
            total_items=len(status) + len(jobs) + len(findings) + len(buckets) + len(identifiers),
            details={
                'Macie Status': len(status),
                'Classification Jobs': len(jobs),
                'Findings': len(findings),
                'S3 Buckets': len(buckets),
                'Custom Identifiers': len(identifiers)
            }
        )

    utils.log_script_end(script_name)


if __name__ == "__main__":
    main()
