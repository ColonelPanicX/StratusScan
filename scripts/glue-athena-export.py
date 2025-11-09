#!/usr/bin/env python3
"""
AWS Glue & Athena Export Script for StratusScan

Exports comprehensive AWS Glue (ETL) and Athena (SQL query) service information
including databases, tables, crawlers, jobs, data catalogs, and Athena workgroups.

Features:
- Glue Databases: Data catalog databases with location URIs
- Glue Tables: Schema definitions, partitions, storage formats
- Glue Crawlers: Data discovery configurations and schedules
- Glue Jobs: ETL job definitions, connections, and triggers
- Athena Workgroups: Query execution environments and settings
- Athena Data Catalogs: External catalog connections
- Summary: Resource counts and key metrics

Output: Excel file with 7 worksheets
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


@utils.aws_error_handler("Collecting Glue databases", default_return=[])
def collect_glue_databases(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect AWS Glue database information from AWS regions."""
    all_databases = []

    for region in regions:
        utils.log_info(f"Scanning Glue databases in {region}...")
        glue_client = utils.get_boto3_client('glue', region_name=region)

        paginator = glue_client.get_paginator('get_databases')
        for page in paginator.paginate():
            databases = page.get('DatabaseList', [])

            for db in databases:
                db_name = db.get('Name', 'N/A')
                description = db.get('Description', 'N/A')
                location_uri = db.get('LocationUri', 'N/A')

                # Creation time
                create_time = db.get('CreateTime')
                if create_time:
                    create_time_str = create_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    create_time_str = 'N/A'

                # Catalog ID
                catalog_id = db.get('CatalogId', 'N/A')

                all_databases.append({
                    'Region': region,
                    'Database Name': db_name,
                    'Description': description,
                    'Location URI': location_uri,
                    'Catalog ID': catalog_id,
                    'Created': create_time_str,
                })

        utils.log_success(f"Collected {len([d for d in all_databases if d['Region'] == region])} Glue databases from {region}")

    return all_databases


@utils.aws_error_handler("Collecting Glue tables", default_return=[])
def collect_glue_tables(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect AWS Glue table information from AWS regions."""
    all_tables = []

    for region in regions:
        utils.log_info(f"Scanning Glue tables in {region}...")
        glue_client = utils.get_boto3_client('glue', region_name=region)

        # First get all databases
        try:
            databases_response = glue_client.get_databases()
            databases = databases_response.get('DatabaseList', [])
        except Exception as e:
            utils.log_warning(f"Could not list databases in {region}: {str(e)}")
            continue

        # Then get tables for each database
        for db in databases:
            db_name = db.get('Name', '')

            try:
                paginator = glue_client.get_paginator('get_tables')
                for page in paginator.paginate(DatabaseName=db_name):
                    tables = page.get('TableList', [])

                    for table in tables:
                        table_name = table.get('Name', 'N/A')
                        description = table.get('Description', 'N/A')

                        # Storage descriptor
                        storage_descriptor = table.get('StorageDescriptor', {})
                        location = storage_descriptor.get('Location', 'N/A')
                        input_format = storage_descriptor.get('InputFormat', 'N/A')
                        output_format = storage_descriptor.get('OutputFormat', 'N/A')

                        # Serde info
                        serde_info = storage_descriptor.get('SerdeInfo', {})
                        serialization_library = serde_info.get('SerializationLibrary', 'N/A')

                        # Column count
                        columns = storage_descriptor.get('Columns', [])
                        column_count = len(columns)

                        # Partition keys
                        partition_keys = table.get('PartitionKeys', [])
                        partition_count = len(partition_keys)
                        partition_names = [pk.get('Name', '') for pk in partition_keys]
                        partition_names_str = ', '.join(partition_names) if partition_names else 'None'

                        # Table type
                        table_type = table.get('TableType', 'N/A')

                        # Creation and update times
                        create_time = table.get('CreateTime')
                        if create_time:
                            create_time_str = create_time.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            create_time_str = 'N/A'

                        update_time = table.get('UpdateTime')
                        if update_time:
                            update_time_str = update_time.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            update_time_str = 'N/A'

                        all_tables.append({
                            'Region': region,
                            'Database': db_name,
                            'Table Name': table_name,
                            'Description': description,
                            'Table Type': table_type,
                            'Location': location,
                            'Column Count': column_count,
                            'Partition Keys': partition_names_str,
                            'Partition Count': partition_count,
                            'Input Format': input_format,
                            'Output Format': output_format,
                            'Serialization Library': serialization_library,
                            'Created': create_time_str,
                            'Updated': update_time_str,
                        })

            except Exception as e:
                utils.log_warning(f"Could not get tables for database {db_name}: {str(e)}")
                continue

        utils.log_success(f"Collected {len([t for t in all_tables if t['Region'] == region])} Glue tables from {region}")

    return all_tables


@utils.aws_error_handler("Collecting Glue crawlers", default_return=[])
def collect_glue_crawlers(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect AWS Glue crawler information from AWS regions."""
    all_crawlers = []

    for region in regions:
        utils.log_info(f"Scanning Glue crawlers in {region}...")
        glue_client = utils.get_boto3_client('glue', region_name=region)

        paginator = glue_client.get_paginator('get_crawlers')
        for page in paginator.paginate():
            crawlers = page.get('Crawlers', [])

            for crawler in crawlers:
                crawler_name = crawler.get('Name', 'N/A')
                role = crawler.get('Role', 'N/A')
                if role != 'N/A' and '/' in role:
                    role = role.split('/')[-1]  # Extract role name from ARN

                # Target databases
                database_name = crawler.get('DatabaseName', 'N/A')

                # Targets
                targets = crawler.get('Targets', {})
                s3_targets = targets.get('S3Targets', [])
                s3_target_count = len(s3_targets)
                s3_paths = [t.get('Path', '') for t in s3_targets]
                s3_paths_str = ', '.join(s3_paths[:3]) if s3_paths else 'None'  # Show first 3
                if len(s3_paths) > 3:
                    s3_paths_str += f' (+{len(s3_paths) - 3} more)'

                jdbc_targets = targets.get('JdbcTargets', [])
                jdbc_target_count = len(jdbc_targets)

                dynamodb_targets = targets.get('DynamoDBTargets', [])
                dynamodb_target_count = len(dynamodb_targets)

                # State and schedule
                state = crawler.get('State', 'N/A')
                schedule = crawler.get('Schedule', {})
                schedule_expression = schedule.get('ScheduleExpression', 'N/A') if schedule else 'N/A'

                # Classifiers
                classifiers = crawler.get('Classifiers', [])
                classifiers_str = ', '.join(classifiers) if classifiers else 'Default'

                # Schema change policy
                schema_change_policy = crawler.get('SchemaChangePolicy', {})
                update_behavior = schema_change_policy.get('UpdateBehavior', 'N/A')
                delete_behavior = schema_change_policy.get('DeleteBehavior', 'N/A')

                # Recrawl policy
                recrawl_policy = crawler.get('RecrawlPolicy', {})
                recrawl_behavior = recrawl_policy.get('RecrawlBehavior', 'N/A')

                # Creation time
                creation_time = crawler.get('CreationTime')
                if creation_time:
                    creation_time_str = creation_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    creation_time_str = 'N/A'

                # Last crawl info
                last_crawl = crawler.get('LastCrawl', {})
                last_crawl_status = last_crawl.get('Status', 'Never run') if last_crawl else 'Never run'

                all_crawlers.append({
                    'Region': region,
                    'Crawler Name': crawler_name,
                    'State': state,
                    'Database': database_name,
                    'Role': role,
                    'S3 Targets': s3_target_count,
                    'S3 Paths': s3_paths_str,
                    'JDBC Targets': jdbc_target_count,
                    'DynamoDB Targets': dynamodb_target_count,
                    'Schedule': schedule_expression,
                    'Classifiers': classifiers_str,
                    'Update Behavior': update_behavior,
                    'Delete Behavior': delete_behavior,
                    'Recrawl Behavior': recrawl_behavior,
                    'Last Crawl Status': last_crawl_status,
                    'Created': creation_time_str,
                })

        utils.log_success(f"Collected {len([c for c in all_crawlers if c['Region'] == region])} Glue crawlers from {region}")

    return all_crawlers


@utils.aws_error_handler("Collecting Glue jobs", default_return=[])
def collect_glue_jobs(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect AWS Glue job information from AWS regions."""
    all_jobs = []

    for region in regions:
        utils.log_info(f"Scanning Glue jobs in {region}...")
        glue_client = utils.get_boto3_client('glue', region_name=region)

        paginator = glue_client.get_paginator('get_jobs')
        for page in paginator.paginate():
            jobs = page.get('Jobs', [])

            for job in jobs:
                job_name = job.get('Name', 'N/A')
                description = job.get('Description', 'N/A')
                role = job.get('Role', 'N/A')
                if role != 'N/A' and '/' in role:
                    role = role.split('/')[-1]

                # Command
                command = job.get('Command', {})
                command_name = command.get('Name', 'N/A')
                script_location = command.get('ScriptLocation', 'N/A')
                python_version = command.get('PythonVersion', 'N/A')

                # Execution properties
                max_retries = job.get('MaxRetries', 0)
                timeout = job.get('Timeout', 0)
                max_capacity = job.get('MaxCapacity', 'N/A')

                # Worker configuration
                worker_type = job.get('WorkerType', 'N/A')
                number_of_workers = job.get('NumberOfWorkers', 'N/A')

                # Glue version
                glue_version = job.get('GlueVersion', 'N/A')

                # Connections
                connections = job.get('Connections', {})
                connection_list = connections.get('Connections', [])
                connections_str = ', '.join(connection_list) if connection_list else 'None'

                # Creation time
                created_on = job.get('CreatedOn')
                if created_on:
                    created_on_str = created_on.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    created_on_str = 'N/A'

                # Last modified
                last_modified_on = job.get('LastModifiedOn')
                if last_modified_on:
                    last_modified_on_str = last_modified_on.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    last_modified_on_str = 'N/A'

                all_jobs.append({
                    'Region': region,
                    'Job Name': job_name,
                    'Description': description,
                    'Command': command_name,
                    'Role': role,
                    'Glue Version': glue_version,
                    'Worker Type': worker_type,
                    'Number of Workers': number_of_workers,
                    'Max Capacity': max_capacity,
                    'Python Version': python_version,
                    'Script Location': script_location,
                    'Max Retries': max_retries,
                    'Timeout (min)': timeout,
                    'Connections': connections_str,
                    'Created': created_on_str,
                    'Last Modified': last_modified_on_str,
                })

        utils.log_success(f"Collected {len([j for j in all_jobs if j['Region'] == region])} Glue jobs from {region}")

    return all_jobs


@utils.aws_error_handler("Collecting Athena workgroups", default_return=[])
def collect_athena_workgroups(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect Athena workgroup information from AWS regions."""
    all_workgroups = []

    for region in regions:
        utils.log_info(f"Scanning Athena workgroups in {region}...")
        athena_client = utils.get_boto3_client('athena', region_name=region)

        paginator = athena_client.get_paginator('list_work_groups')
        for page in paginator.paginate():
            workgroups = page.get('WorkGroups', [])

            for wg_summary in workgroups:
                workgroup_name = wg_summary.get('Name', 'N/A')

                # Get detailed workgroup information
                try:
                    wg_response = athena_client.get_work_group(WorkGroup=workgroup_name)
                    wg = wg_response.get('WorkGroup', {})

                    state = wg.get('State', 'N/A')
                    description = wg.get('Description', 'N/A')

                    # Configuration
                    configuration = wg.get('Configuration', {})
                    result_config = configuration.get('ResultConfiguration', {})
                    output_location = result_config.get('OutputLocation', 'N/A')

                    # Encryption
                    encryption_config = result_config.get('EncryptionConfiguration', {})
                    encryption_option = encryption_config.get('EncryptionOption', 'None')
                    kms_key = encryption_config.get('KmsKey', 'N/A') if encryption_option != 'None' else 'N/A'

                    # Bytes scanned cutoff
                    bytes_scanned_cutoff = configuration.get('BytesScannedCutoffPerQuery', 'N/A')

                    # Enforce configuration
                    enforce_workgroup_config = configuration.get('EnforceWorkGroupConfiguration', False)

                    # Publish CloudWatch metrics
                    publish_cloudwatch_metrics = configuration.get('PublishCloudWatchMetricsEnabled', False)

                    # Requester pays
                    requester_pays_enabled = configuration.get('RequesterPaysEnabled', False)

                    # Engine version
                    engine_version = configuration.get('EngineVersion', {})
                    engine_version_str = engine_version.get('SelectedEngineVersion', 'N/A') if engine_version else 'N/A'

                    # Creation time
                    creation_time = wg.get('CreationTime')
                    if creation_time:
                        creation_time_str = creation_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        creation_time_str = 'N/A'

                    all_workgroups.append({
                        'Region': region,
                        'Workgroup Name': workgroup_name,
                        'State': state,
                        'Description': description,
                        'Output Location': output_location,
                        'Encryption': encryption_option,
                        'KMS Key': kms_key,
                        'Bytes Scanned Cutoff': bytes_scanned_cutoff,
                        'Enforce Config': 'Yes' if enforce_workgroup_config else 'No',
                        'CloudWatch Metrics': 'Yes' if publish_cloudwatch_metrics else 'No',
                        'Requester Pays': 'Yes' if requester_pays_enabled else 'No',
                        'Engine Version': engine_version_str,
                        'Created': creation_time_str,
                    })

                except Exception as e:
                    utils.log_warning(f"Could not get details for workgroup {workgroup_name}: {str(e)}")
                    continue

        utils.log_success(f"Collected {len([wg for wg in all_workgroups if wg['Region'] == region])} Athena workgroups from {region}")

    return all_workgroups


@utils.aws_error_handler("Collecting Athena data catalogs", default_return=[])
def collect_athena_data_catalogs(regions: List[str]) -> List[Dict[str, Any]]:
    """Collect Athena data catalog information from AWS regions."""
    all_catalogs = []

    for region in regions:
        utils.log_info(f"Scanning Athena data catalogs in {region}...")
        athena_client = utils.get_boto3_client('athena', region_name=region)

        paginator = athena_client.get_paginator('list_data_catalogs')
        for page in paginator.paginate():
            catalogs = page.get('DataCatalogsSummary', [])

            for catalog_summary in catalogs:
                catalog_name = catalog_summary.get('CatalogName', 'N/A')
                catalog_type = catalog_summary.get('Type', 'N/A')

                # Get detailed catalog information
                try:
                    catalog_response = athena_client.get_data_catalog(Name=catalog_name)
                    catalog = catalog_response.get('DataCatalog', {})

                    description = catalog.get('Description', 'N/A')
                    catalog_type_detailed = catalog.get('Type', 'N/A')

                    # Parameters (connection details for external catalogs)
                    parameters = catalog.get('Parameters', {})
                    parameters_str = ', '.join([f"{k}={v}" for k, v in parameters.items()]) if parameters else 'None'

                    all_catalogs.append({
                        'Region': region,
                        'Catalog Name': catalog_name,
                        'Type': catalog_type_detailed,
                        'Description': description,
                        'Parameters': parameters_str,
                    })

                except Exception as e:
                    utils.log_warning(f"Could not get details for catalog {catalog_name}: {str(e)}")
                    continue

        utils.log_success(f"Collected {len([c for c in all_catalogs if c['Region'] == region])} Athena data catalogs from {region}")

    return all_catalogs


def generate_summary(databases: List[Dict[str, Any]],
                     tables: List[Dict[str, Any]],
                     crawlers: List[Dict[str, Any]],
                     jobs: List[Dict[str, Any]],
                     workgroups: List[Dict[str, Any]],
                     catalogs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate summary statistics for Glue and Athena resources."""
    summary = []

    # Glue resources
    summary.append({
        'Metric': 'Total Glue Databases',
        'Count': len(databases),
        'Details': f"{len(databases)} databases in Glue Data Catalog"
    })

    summary.append({
        'Metric': 'Total Glue Tables',
        'Count': len(tables),
        'Details': f"{len(tables)} tables across all databases"
    })

    summary.append({
        'Metric': 'Total Glue Crawlers',
        'Count': len(crawlers),
        'Details': f"{len([c for c in crawlers if c['State'] == 'READY'])} ready"
    })

    summary.append({
        'Metric': 'Total Glue Jobs',
        'Count': len(jobs),
        'Details': f"{len(jobs)} ETL jobs configured"
    })

    # Athena resources
    summary.append({
        'Metric': 'Total Athena Workgroups',
        'Count': len(workgroups),
        'Details': f"{len([wg for wg in workgroups if wg['State'] == 'ENABLED'])} enabled"
    })

    summary.append({
        'Metric': 'Total Athena Data Catalogs',
        'Count': len(catalogs),
        'Details': f"{len(catalogs)} data catalogs configured"
    })

    # Tables by database
    if tables:
        db_counts = {}
        for table in tables:
            db = table['Database']
            db_counts[db] = db_counts.get(db, 0) + 1

        top_dbs = sorted(db_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        db_details = ', '.join([f"{db}: {count}" for db, count in top_dbs])
        summary.append({
            'Metric': 'Top Databases by Table Count',
            'Count': len(db_counts),
            'Details': db_details
        })

    # Crawler targets
    if crawlers:
        total_s3_targets = sum(c['S3 Targets'] for c in crawlers if isinstance(c['S3 Targets'], int))
        total_jdbc_targets = sum(c['JDBC Targets'] for c in crawlers if isinstance(c['JDBC Targets'], int))
        total_dynamodb_targets = sum(c['DynamoDB Targets'] for c in crawlers if isinstance(c['DynamoDB Targets'], int))

        summary.append({
            'Metric': 'Crawler Targets',
            'Count': total_s3_targets + total_jdbc_targets + total_dynamodb_targets,
            'Details': f"S3: {total_s3_targets}, JDBC: {total_jdbc_targets}, DynamoDB: {total_dynamodb_targets}"
        })

    # Athena encryption
    if workgroups:
        encrypted_workgroups = len([wg for wg in workgroups if wg['Encryption'] != 'None'])
        summary.append({
            'Metric': 'Encrypted Athena Workgroups',
            'Count': encrypted_workgroups,
            'Details': f"{encrypted_workgroups}/{len(workgroups)} workgroups with encryption"
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
        regions = utils.get_all_aws_regions('glue')
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
    print("\n=== Collecting Glue & Athena Data ===")
    databases = collect_glue_databases(regions)
    tables = collect_glue_tables(regions)
    crawlers = collect_glue_crawlers(regions)
    jobs = collect_glue_jobs(regions)
    workgroups = collect_athena_workgroups(regions)
    catalogs = collect_athena_data_catalogs(regions)

    # Generate summary
    summary = generate_summary(databases, tables, crawlers, jobs, workgroups, catalogs)

    # Convert to DataFrames
    databases_df = pd.DataFrame(databases) if databases else pd.DataFrame()
    tables_df = pd.DataFrame(tables) if tables else pd.DataFrame()
    crawlers_df = pd.DataFrame(crawlers) if crawlers else pd.DataFrame()
    jobs_df = pd.DataFrame(jobs) if jobs else pd.DataFrame()
    workgroups_df = pd.DataFrame(workgroups) if workgroups else pd.DataFrame()
    catalogs_df = pd.DataFrame(catalogs) if catalogs else pd.DataFrame()
    summary_df = pd.DataFrame(summary)

    # Prepare DataFrames for export
    if not databases_df.empty:
        databases_df = utils.prepare_dataframe_for_export(databases_df)
    if not tables_df.empty:
        tables_df = utils.prepare_dataframe_for_export(tables_df)
    if not crawlers_df.empty:
        crawlers_df = utils.prepare_dataframe_for_export(crawlers_df)
    if not jobs_df.empty:
        jobs_df = utils.prepare_dataframe_for_export(jobs_df)
    if not workgroups_df.empty:
        workgroups_df = utils.prepare_dataframe_for_export(workgroups_df)
    if not catalogs_df.empty:
        catalogs_df = utils.prepare_dataframe_for_export(catalogs_df)
    if not summary_df.empty:
        summary_df = utils.prepare_dataframe_for_export(summary_df)

    # Create export filename
    region_suffix = regions[0] if len(regions) == 1 else 'all-regions'
    filename = utils.create_export_filename(account_name, 'glue-athena', region_suffix)

    # Save to Excel with multiple sheets
    print("\n=== Exporting to Excel ===")
    dataframes = {
        'Glue Databases': databases_df,
        'Glue Tables': tables_df,
        'Glue Crawlers': crawlers_df,
        'Glue Jobs': jobs_df,
        'Athena Workgroups': workgroups_df,
        'Athena Data Catalogs': catalogs_df,
        'Summary': summary_df
    }

    if utils.save_multiple_dataframes_to_excel(dataframes, filename):
        utils.log_export_summary(
            filename=filename,
            total_items=len(databases) + len(tables) + len(crawlers) + len(jobs) + len(workgroups) + len(catalogs),
            details={
                'Glue Databases': len(databases),
                'Glue Tables': len(tables),
                'Glue Crawlers': len(crawlers),
                'Glue Jobs': len(jobs),
                'Athena Workgroups': len(workgroups),
                'Athena Data Catalogs': len(catalogs)
            }
        )

    utils.log_script_end(script_name)


if __name__ == "__main__":
    main()
