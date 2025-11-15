#!/usr/bin/env python3
"""
AWS CodeBuild Export Script for StratusScan

Exports comprehensive AWS CodeBuild CI/CD information including:
- Build projects with source and artifact configurations
- Recent builds with status and duration
- Source credentials and webhooks
- Report groups for test and code coverage reports

Output: Multi-worksheet Excel file with CodeBuild resources
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import json

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
    print("Error: pandas is not installed. Please install it using 'pip install pandas'")
    sys.exit(1)


def check_dependencies():
    """Check if required dependencies are installed."""
    utils.log_info("Checking dependencies...")

    missing = []

    try:
        import pandas
        utils.log_info("✓ pandas is installed")
    except ImportError:
        missing.append("pandas")

    try:
        import openpyxl
        utils.log_info("✓ openpyxl is installed")
    except ImportError:
        missing.append("openpyxl")

    try:
        import boto3
        utils.log_info("✓ boto3 is installed")
    except ImportError:
        missing.append("boto3")

    if missing:
        utils.log_error(f"Missing dependencies: {', '.join(missing)}")
        utils.log_error("Please install using: pip install " + " ".join(missing))
        sys.exit(1)

    utils.log_success("All dependencies are installed")


@utils.aws_error_handler("Collecting CodeBuild projects", default_return=[])
def collect_projects(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect CodeBuild project information from AWS regions."""
    all_projects = []

    for region in regions:
        utils.log_info(f"Collecting CodeBuild projects in {region}...")
        codebuild_client = utils.get_boto3_client('codebuild', region_name=region)

        try:
            # List all projects
            paginator = codebuild_client.get_paginator('list_projects')
            project_names = []
            for page in paginator.paginate():
                project_names.extend(page.get('projects', []))

            utils.log_info(f"Found {len(project_names)} projects in {region}")

            # Batch get project details (100 at a time)
            for i in range(0, len(project_names), 100):
                batch = project_names[i:i+100]
                projects_response = codebuild_client.batch_get_projects(names=batch)
                projects = projects_response.get('projects', [])

                for project in projects:
                    project_name = project.get('name', 'N/A')
                    arn = project.get('arn', 'N/A')
                    description = project.get('description', 'N/A')

                    created = project.get('created', 'N/A')
                    if created != 'N/A':
                        created = created.strftime('%Y-%m-%d %H:%M:%S')

                    last_modified = project.get('lastModified', 'N/A')
                    if last_modified != 'N/A':
                        last_modified = last_modified.strftime('%Y-%m-%d %H:%M:%S')

                    # Source configuration
                    source = project.get('source', {})
                    source_type = source.get('type', 'N/A')
                    source_location = source.get('location', 'N/A')
                    buildspec = source.get('buildspec', 'Inline/Default')
                    git_clone_depth = source.get('gitCloneDepth', 'N/A')

                    # Environment
                    environment = project.get('environment', {})
                    env_type = environment.get('type', 'N/A')
                    compute_type = environment.get('computeType', 'N/A')
                    image = environment.get('image', 'N/A')
                    privileged_mode = environment.get('privilegedMode', False)

                    # Service role
                    service_role = project.get('serviceRole', 'N/A')

                    # Artifacts
                    artifacts = project.get('artifacts', {})
                    artifacts_type = artifacts.get('type', 'N/A')
                    artifacts_location = artifacts.get('location', 'N/A')

                    # Cache
                    cache = project.get('cache', {})
                    cache_type = cache.get('type', 'NO_CACHE')
                    cache_location = cache.get('location', 'N/A')

                    # VPC config
                    vpc_config = project.get('vpcConfig', {})
                    vpc_id = vpc_config.get('vpcId', 'N/A')
                    subnets = vpc_config.get('subnets', [])
                    vpc_enabled = 'Yes' if vpc_id != 'N/A' else 'No'

                    # Timeout
                    timeout_minutes = project.get('timeoutInMinutes', 'N/A')
                    queued_timeout = project.get('queuedTimeoutInMinutes', 'N/A')

                    # Badge
                    badge = project.get('badge', {})
                    badge_enabled = badge.get('badgeEnabled', False)

                    # Logs
                    logs_config = project.get('logsConfig', {})
                    cloudwatch_logs = logs_config.get('cloudWatchLogs', {})
                    s3_logs = logs_config.get('s3Logs', {})
                    cw_logs_status = cloudwatch_logs.get('status', 'DISABLED')
                    s3_logs_status = s3_logs.get('status', 'DISABLED')

                    # Webhook
                    webhook = project.get('webhook', {})
                    webhook_url = webhook.get('url', 'N/A')

                    all_projects.append({
                        'Region': region,
                        'Project Name': project_name,
                        'ARN': arn,
                        'Description': description,
                        'Created': created,
                        'Last Modified': last_modified,
                        'Source Type': source_type,
                        'Source Location': source_location,
                        'Buildspec': buildspec,
                        'Git Clone Depth': git_clone_depth,
                        'Environment Type': env_type,
                        'Compute Type': compute_type,
                        'Image': image,
                        'Privileged Mode': privileged_mode,
                        'Service Role': service_role,
                        'Artifacts Type': artifacts_type,
                        'Artifacts Location': artifacts_location,
                        'Cache Type': cache_type,
                        'Cache Location': cache_location,
                        'VPC Enabled': vpc_enabled,
                        'VPC ID': vpc_id,
                        'Timeout (minutes)': timeout_minutes,
                        'Queued Timeout (minutes)': queued_timeout,
                        'Badge Enabled': badge_enabled,
                        'CloudWatch Logs': cw_logs_status,
                        'S3 Logs': s3_logs_status,
                        'Webhook URL': webhook_url
                    })

        except Exception as e:
            utils.log_warning(f"Error collecting CodeBuild projects in {region}: {str(e)}")
            continue

    utils.log_info(f"Collected {len(all_projects)} CodeBuild projects")
    return all_projects


@utils.aws_error_handler("Collecting CodeBuild builds", default_return=[])
def collect_builds(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect recent CodeBuild build information (limited to 50 most recent per region)."""
    all_builds = []

    for region in regions:
        utils.log_info(f"Collecting recent builds in {region}...")
        codebuild_client = utils.get_boto3_client('codebuild', region_name=region)

        try:
            # List build IDs (sorted by start time descending)
            build_ids = []
            paginator = codebuild_client.get_paginator('list_builds')
            for page in paginator.paginate(sortOrder='DESCENDING'):
                build_ids.extend(page.get('ids', []))
                if len(build_ids) >= 50:
                    break

            # Limit to 50 most recent
            build_ids = build_ids[:50]

            if not build_ids:
                continue

            utils.log_info(f"Found {len(build_ids)} recent builds in {region}")

            # Batch get build details (100 at a time)
            for i in range(0, len(build_ids), 100):
                batch = build_ids[i:i+100]
                builds_response = codebuild_client.batch_get_builds(ids=batch)
                builds = builds_response.get('builds', [])

                for build in builds:
                    build_id = build.get('id', 'N/A')
                    arn = build.get('arn', 'N/A')
                    build_number = build.get('buildNumber', 'N/A')
                    project_name = build.get('projectName', 'N/A')
                    build_status = build.get('buildStatus', 'N/A')
                    current_phase = build.get('currentPhase', 'N/A')

                    # Times
                    start_time = build.get('startTime', 'N/A')
                    if start_time != 'N/A':
                        start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')

                    end_time = build.get('endTime', 'N/A')
                    if end_time != 'N/A':
                        end_time = end_time.strftime('%Y-%m-%d %H:%M:%S')

                    # Duration
                    build_complete = build.get('buildComplete', False)
                    if build_complete:
                        start_dt = build.get('startTime')
                        end_dt = build.get('endTime')
                        if start_dt and end_dt:
                            duration_seconds = (end_dt - start_dt).total_seconds()
                            duration_minutes = duration_seconds / 60
                            duration_str = f"{duration_minutes:.1f} minutes"
                        else:
                            duration_str = 'N/A'
                    else:
                        duration_str = 'In Progress'

                    # Source
                    source = build.get('source', {})
                    source_type = source.get('type', 'N/A')
                    source_location = source.get('location', 'N/A')

                    # Source version
                    source_version = build.get('sourceVersion', 'N/A')
                    resolved_source_version = build.get('resolvedSourceVersion', 'N/A')

                    # Initiator
                    initiator = build.get('initiator', 'N/A')

                    # Environment
                    environment = build.get('environment', {})
                    compute_type = environment.get('computeType', 'N/A')
                    image = environment.get('image', 'N/A')

                    # Logs
                    logs = build.get('logs', {})
                    logs_deep_link = logs.get('deepLink', 'N/A')

                    all_builds.append({
                        'Region': region,
                        'Build ID': build_id,
                        'Build Number': build_number,
                        'Project Name': project_name,
                        'Status': build_status,
                        'Current Phase': current_phase,
                        'Started': start_time,
                        'Ended': end_time,
                        'Duration': duration_str,
                        'Source Type': source_type,
                        'Source Location': source_location,
                        'Source Version': source_version,
                        'Resolved Source Version': resolved_source_version,
                        'Initiator': initiator,
                        'Compute Type': compute_type,
                        'Image': image,
                        'Logs': logs_deep_link
                    })

        except Exception as e:
            utils.log_warning(f"Error collecting builds in {region}: {str(e)}")
            continue

    utils.log_info(f"Collected {len(all_builds)} builds (limited to 50 most recent per region)")
    return all_builds


@utils.aws_error_handler("Collecting CodeBuild report groups", default_return=[])
def collect_report_groups(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect CodeBuild report group information."""
    all_report_groups = []

    for region in regions:
        utils.log_info(f"Collecting report groups in {region}...")
        codebuild_client = utils.get_boto3_client('codebuild', region_name=region)

        try:
            # List report groups
            paginator = codebuild_client.get_paginator('list_report_groups')
            report_group_arns = []
            for page in paginator.paginate():
                report_group_arns.extend(page.get('reportGroups', []))

            if not report_group_arns:
                continue

            utils.log_info(f"Found {len(report_group_arns)} report groups in {region}")

            # Batch get report group details (100 at a time)
            for i in range(0, len(report_group_arns), 100):
                batch = report_group_arns[i:i+100]
                groups_response = codebuild_client.batch_get_report_groups(reportGroupArns=batch)
                groups = groups_response.get('reportGroups', [])

                for group in groups:
                    arn = group.get('arn', 'N/A')
                    name = group.get('name', 'N/A')
                    group_type = group.get('type', 'N/A')
                    status = group.get('status', 'N/A')

                    created = group.get('created', 'N/A')
                    if created != 'N/A':
                        created = created.strftime('%Y-%m-%d %H:%M:%S')

                    last_modified = group.get('lastModified', 'N/A')
                    if last_modified != 'N/A':
                        last_modified = last_modified.strftime('%Y-%m-%d %H:%M:%S')

                    # Export config
                    export_config = group.get('exportConfig', {})
                    export_type = export_config.get('exportConfigType', 'N/A')

                    s3_destination = export_config.get('s3Destination', {})
                    s3_bucket = s3_destination.get('bucket', 'N/A')
                    s3_path = s3_destination.get('path', 'N/A')

                    all_report_groups.append({
                        'Region': region,
                        'Name': name,
                        'ARN': arn,
                        'Type': group_type,
                        'Status': status,
                        'Created': created,
                        'Last Modified': last_modified,
                        'Export Type': export_type,
                        'S3 Bucket': s3_bucket,
                        'S3 Path': s3_path
                    })

        except Exception as e:
            utils.log_warning(f"Error collecting report groups in {region}: {str(e)}")
            continue

    utils.log_info(f"Collected {len(all_report_groups)} report groups")
    return all_report_groups


def generate_summary(projects: List[Dict[str, Any]],
                     builds: List[Dict[str, Any]],
                     report_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate summary statistics for CodeBuild resources."""
    utils.log_info("Generating summary statistics...")

    summary = []

    # Projects summary
    total_projects = len(projects)
    summary.append({
        'Metric': 'Total Build Projects',
        'Count': total_projects,
        'Details': 'CodeBuild CI/CD projects'
    })

    # Source types
    if projects:
        df = pd.DataFrame(projects)
        source_types = df['Source Type'].value_counts().to_dict()
        for source_type, count in source_types.items():
            summary.append({
                'Metric': f'Projects - {source_type}',
                'Count': count,
                'Details': 'Source repository type'
            })

    # VPC enabled
    vpc_enabled = sum(1 for p in projects if p.get('VPC Enabled', 'No') == 'Yes')
    if vpc_enabled > 0:
        summary.append({
            'Metric': 'Projects with VPC',
            'Count': vpc_enabled,
            'Details': 'Projects running in VPC for private resource access'
        })

    # Privileged mode
    privileged_projects = sum(1 for p in projects if p.get('Privileged Mode', False))
    if privileged_projects > 0:
        summary.append({
            'Metric': '⚠️ Projects with Privileged Mode',
            'Count': privileged_projects,
            'Details': 'SECURITY: Docker privileged mode enabled - review necessity'
        })

    # Builds summary
    total_builds = len(builds)
    succeeded_builds = sum(1 for b in builds if b.get('Status', '') == 'SUCCEEDED')
    failed_builds = sum(1 for b in builds if b.get('Status', '') == 'FAILED')
    in_progress = sum(1 for b in builds if b.get('Status', '') == 'IN_PROGRESS')

    summary.append({
        'Metric': 'Recent Builds (Sample)',
        'Count': total_builds,
        'Details': f'Succeeded: {succeeded_builds}, Failed: {failed_builds}, In Progress: {in_progress}'
    })

    # Report groups
    total_report_groups = len(report_groups)
    summary.append({
        'Metric': 'Total Report Groups',
        'Count': total_report_groups,
        'Details': 'Test and code coverage report configurations'
    })

    # Regional distribution
    if projects:
        df = pd.DataFrame(projects)
        regions = df['Region'].value_counts().to_dict()
        for region, count in regions.items():
            summary.append({
                'Metric': f'Projects in {region}',
                'Count': count,
                'Details': 'Regional distribution'
            })

    return summary


def main():
    """Main execution function."""
    script_name = Path(__file__).stem
    utils.setup_logging(script_name)
    utils.log_script_start(script_name)

    print("\n" + "="*60)
    print("AWS CodeBuild Export Tool")
    print("="*60)

    # Check dependencies
    check_dependencies()

    # Get AWS account information
    account_id, account_name = utils.get_account_info()
    if not account_id:
        utils.log_error("Unable to determine AWS account ID. Please check your credentials.")
        return

    utils.log_info(f"AWS Account: {account_name} ({account_id})")

    # Region selection
    print("\nRegion Selection:")
    print("1. All regions")
    print("2. Specific region")

    choice = input("\nEnter your choice (1-2): ").strip()

    if choice == '1':
        regions = utils.get_all_aws_regions(service_code='codebuild')
        utils.log_info(f"Selected all regions: {len(regions)} regions")
    elif choice == '2':
        region = input("Enter AWS region (e.g., us-east-1): ").strip()
        if not utils.validate_aws_region(region):
            utils.log_error(f"Invalid region: {region}")
            return
        regions = [region]
    else:
        utils.log_error("Invalid choice")
        return

    # Collect data
    print("\nCollecting AWS CodeBuild data...")

    projects = collect_projects(regions)
    builds = collect_builds(regions)
    report_groups = collect_report_groups(regions)
    summary = generate_summary(projects, builds, report_groups)

    # Create DataFrames
    utils.log_info("Creating DataFrames...")

    dataframes = {}

    if projects:
        df_projects = pd.DataFrame(projects)
        df_projects = utils.prepare_dataframe_for_export(df_projects)
        dataframes['Build Projects'] = df_projects

    if builds:
        df_builds = pd.DataFrame(builds)
        df_builds = utils.prepare_dataframe_for_export(df_builds)
        dataframes['Recent Builds'] = df_builds

    if report_groups:
        df_report_groups = pd.DataFrame(report_groups)
        df_report_groups = utils.prepare_dataframe_for_export(df_report_groups)
        dataframes['Report Groups'] = df_report_groups

    if summary:
        df_summary = pd.DataFrame(summary)
        df_summary = utils.prepare_dataframe_for_export(df_summary)
        dataframes['Summary'] = df_summary

    # Export to Excel
    if dataframes:
        region_suffix = 'all-regions' if len(regions) > 1 else regions[0]
        filename = utils.create_export_filename(account_name, 'codebuild', region_suffix)

        utils.log_info(f"Exporting to {filename}...")
        utils.save_multiple_dataframes_to_excel(dataframes, filename)

        # Log summary
        utils.log_export_summary(filename, {
            'Build Projects': len(projects),
            'Recent Builds': len(builds),
            'Report Groups': len(report_groups)
        })
    else:
        utils.log_warning("No AWS CodeBuild data found to export")

    utils.log_success("AWS CodeBuild export completed successfully")


if __name__ == "__main__":
    main()
