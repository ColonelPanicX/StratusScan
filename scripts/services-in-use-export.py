#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Services In Use Discovery Script
Version: v2.0.0
Date: SEP-24-2025

Description:
This script discovers and exports all AWS services currently in use within AWS
environments, including both services that incur costs and those that are free. It provides
comprehensive service discovery across all available AWS regions and generates detailed
reports for inventory, compliance, and cost management purposes.

Service Discovery Methods:
- CloudTrail event analysis for service usage patterns
- Cost and Usage Reports for billing services
- Resource enumeration across major AWS services
- API activity monitoring and service detection
- Regional service availability verification
"""

import os
import sys
import boto3
import datetime
import time
import json
from pathlib import Path
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

# Add path to import utils module
try:
    # Try to import directly (if utils.py is in Python path)
    import utils
except ImportError:
    # If import fails, try to find the module relative to this script
    script_dir = Path(__file__).parent.absolute()

    # Check if we're in the scripts directory
    if script_dir.name.lower() == 'scripts':
        # Add the parent directory (StratusScan root) to the path
        sys.path.append(str(script_dir.parent))
    else:
        # Add the current directory to the path
        sys.path.append(str(script_dir))

    # Try import again
    try:
        import utils
    except ImportError:
        print("ERROR: Could not import the utils module. Make sure utils.py is in the StratusScan directory.")
        sys.exit(1)

# Initialize logging for this script
utils.setup_logging("services-in-use-export", log_to_file=True)

def check_dependencies():
    """
    Check if required dependencies are installed and offer to install them if missing.

    Returns:
        bool: True if all dependencies are satisfied, False otherwise
    """
    required_packages = ['pandas', 'openpyxl']
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            utils.log_info(f"[OK] {package} is already installed")
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        utils.log_warning(f"Packages required but not installed: {', '.join(missing_packages)}")
        response = input("Would you like to install these packages now? (y/n): ").lower().strip()

        if response == 'y':
            import subprocess
            for package in missing_packages:
                utils.log_info(f"Installing {package}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    utils.log_success(f"{package} installed successfully")
                except subprocess.CalledProcessError as e:
                    utils.log_error(f"Error installing {package}", e)
                    return False
        else:
            print("Cannot continue without required packages. Exiting.")
            return False

    return True

@utils.aws_error_handler("Getting account information", default_return=("Unknown", "Unknown-AWS-Account"))
def get_account_info():
    """
    Get the current AWS account ID and name with AWS validation.

    Returns:
        tuple: (account_id, account_name)
    """
    sts = utils.get_boto3_client('sts')
    account_id = sts.get_caller_identity()['Account']

    # Validate AWS environment
    caller_arn = sts.get_caller_identity()['Arn']
    account_name = utils.get_account_name(account_id, default=f"AWS-ACCOUNT-{account_id}")

    return account_id, account_name

def print_title():
    """
    Print the script title and account information.

    Returns:
        tuple: (account_id, account_name)
    """
    print("====================================================================")
    print("                   AWS RESOURCE SCANNER                            ")
    print("====================================================================")
    print("AWS SERVICES IN USE DISCOVERY")
    print("====================================================================")
    print("Version: v2.0.0                       Date: SEP-24-2025")
    print("Environment: AWS Commercial")
    print("====================================================================")

    # Get account information
    account_id, account_name = get_account_info()
    print(f"Account ID: {account_id}")
    print(f"Account Name: {account_name}")
    print("====================================================================")

    return account_id, account_name

def get_services_from_cost_explorer():
    """
    Get services that have incurred costs using Cost Explorer API.

    Returns:
        dict: Dictionary of services with cost information
    """
    services_with_costs = {}

    try:
        ce_client = utils.get_boto3_client('ce', region_name='us-west-2')

        # Get cost data for the last 12 months
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=365)

        utils.log_info("Analyzing Cost Explorer data for services with billing activity...")

        response = ce_client.get_dimension_values(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Dimension='SERVICE',
            Context='COST_AND_USAGE'
        )

        for service in response.get('DimensionValues', []):
            service_name = service.get('Value', 'Unknown')
            services_with_costs[service_name] = {
                'has_costs': True,
                'source': 'Cost Explorer',
                'last_detected': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        utils.log_info(f"Found {len(services_with_costs)} services with cost data")

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            utils.log_warning("Access denied to Cost Explorer. Cost data will not be included.")
        else:
            utils.log_warning(f"Error accessing Cost Explorer: {e}")
    except Exception as e:
        utils.log_warning(f"Error getting cost data: {e}")

    return services_with_costs

def discover_services_by_resource_enumeration():
    """
    Discover services by checking for resources across major AWS services.

    Returns:
        dict: Dictionary of discovered services
    """
    discovered_services = {}

    # Define service checks with their detection methods
    service_checks = {
        'Amazon Elastic Compute Cloud - Compute': {
            'client': 'ec2',
            'method': 'describe_instances',
            'check_function': lambda client: len(client.describe_instances()['Reservations']) > 0
        },
        'Amazon Simple Storage Service': {
            'client': 's3',
            'method': 'list_buckets',
            'check_function': lambda client: len(client.list_buckets()['Buckets']) > 0
        },
        'Amazon Relational Database Service': {
            'client': 'rds',
            'method': 'describe_db_instances',
            'check_function': lambda client: len(client.describe_db_instances()['DBInstances']) > 0
        },
        'Amazon Virtual Private Cloud': {
            'client': 'ec2',
            'method': 'describe_vpcs',
            'check_function': lambda client: len([vpc for vpc in client.describe_vpcs()['Vpcs'] if not vpc.get('IsDefault', False)]) > 0
        },
        'AWS Identity and Access Management': {
            'client': 'iam',
            'method': 'list_users',
            'check_function': lambda client: len(client.list_users()['Users']) > 0,
            'region_independent': True
        },
        'Amazon CloudWatch': {
            'client': 'cloudwatch',
            'method': 'list_metrics',
            'check_function': lambda client: len(client.list_metrics(MaxRecords=1)['Metrics']) > 0
        },
        'AWS CloudTrail': {
            'client': 'cloudtrail',
            'method': 'describe_trails',
            'check_function': lambda client: len(client.describe_trails()['trailList']) > 0
        },
        'Amazon Elastic Load Balancing': {
            'client': 'elbv2',
            'method': 'describe_load_balancers',
            'check_function': lambda client: len(client.describe_load_balancers()['LoadBalancers']) > 0
        },
        'Amazon Route 53': {
            'client': 'route53',
            'method': 'list_hosted_zones',
            'check_function': lambda client: len(client.list_hosted_zones()['HostedZones']) > 0,
            'region_independent': True
        },
        'AWS Lambda': {
            'client': 'lambda',
            'method': 'list_functions',
            'check_function': lambda client: len(client.list_functions()['Functions']) > 0
        },
        'Amazon CloudFront': {
            'client': 'cloudfront',
            'method': 'list_distributions',
            'check_function': lambda client: len(client.list_distributions().get('DistributionList', {}).get('Items', [])) > 0,
            'region_independent': True
        },
        'Amazon SNS': {
            'client': 'sns',
            'method': 'list_topics',
            'check_function': lambda client: len(client.list_topics()['Topics']) > 0
        },
        'Amazon SQS': {
            'client': 'sqs',
            'method': 'list_queues',
            'check_function': lambda client: len(client.list_queues().get('QueueUrls', [])) > 0
        },
        'AWS Config': {
            'client': 'config',
            'method': 'describe_configuration_recorders',
            'check_function': lambda client: len(client.describe_configuration_recorders()['ConfigurationRecorders']) > 0
        },
        'Amazon GuardDuty': {
            'client': 'guardduty',
            'method': 'list_detectors',
            'check_function': lambda client: len(client.list_detectors()['DetectorIds']) > 0
        },
        'AWS Security Hub': {
            'client': 'securityhub',
            'method': 'describe_hub',
            'check_function': lambda client: client.describe_hub() is not None
        },
        'AWS Systems Manager': {
            'client': 'ssm',
            'method': 'describe_instance_information',
            'check_function': lambda client: len(client.describe_instance_information()['InstanceInformationList']) > 0
        },
        'Amazon DynamoDB': {
            'client': 'dynamodb',
            'method': 'list_tables',
            'check_function': lambda client: len(client.list_tables()['TableNames']) > 0
        },
        'AWS Key Management Service': {
            'client': 'kms',
            'method': 'list_keys',
            'check_function': lambda client: len(client.list_keys()['Keys']) > 0
        },
        'Amazon Elastic Container Service': {
            'client': 'ecs',
            'method': 'list_clusters',
            'check_function': lambda client: len(client.list_clusters()['clusterArns']) > 0
        },
        'Amazon Elastic Kubernetes Service': {
            'client': 'eks',
            'method': 'list_clusters',
            'check_function': lambda client: len(client.list_clusters()['clusters']) > 0
        },
        'Amazon ElastiCache': {
            'client': 'elasticache',
            'method': 'describe_cache_clusters',
            'check_function': lambda client: len(client.describe_cache_clusters()['CacheClusters']) > 0
        },
        'Amazon Redshift': {
            'client': 'redshift',
            'method': 'describe_clusters',
            'check_function': lambda client: len(client.describe_clusters()['Clusters']) > 0
        }
    }

    regions = utils.get_default_regions()
    total_checks = len(service_checks) * len(regions)
    current_check = 0

    for service_name, check_config in service_checks.items():
        try:
            service_detected = False
            regions_detected = []

            # Some services are region-independent
            check_regions = ['us-west-2'] if check_config.get('region_independent') else regions

            for region in check_regions:
                current_check += 1
                progress = (current_check / total_checks) * 100

                utils.log_info(f"[{progress:.1f}%] Checking {service_name} in {region}")

                try:
                    client = utils.get_boto3_client(check_config['client'], region_name=region)

                    if check_config['check_function'](client):
                        service_detected = True
                        regions_detected.append(region)

                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                        utils.log_warning(f"Access denied for {service_name} in {region}")
                    elif error_code == 'OptInRequired':
                        utils.log_info(f"{service_name} not opted in for {region}")
                    else:
                        utils.log_warning(f"Error checking {service_name} in {region}: {error_code}")
                except EndpointConnectionError:
                    utils.log_warning(f"Service {service_name} not available in {region}")
                except Exception as e:
                    utils.log_warning(f"Error checking {service_name} in {region}: {e}")

            if service_detected:
                discovered_services[service_name] = {
                    'has_costs': False,  # Will be updated if found in cost data
                    'source': 'Resource Enumeration',
                    'regions': regions_detected,
                    'last_detected': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

        except Exception as e:
            utils.log_warning(f"Error setting up check for {service_name}: {e}")

    return discovered_services

def get_services_from_cloudtrail():
    """
    Get services from CloudTrail event history (last 90 days of free event history).

    Returns:
        dict: Dictionary of services detected from CloudTrail
    """
    cloudtrail_services = {}

    try:
        cloudtrail = utils.get_boto3_client('cloudtrail', region_name='us-west-2')

        utils.log_info("Analyzing CloudTrail event history for service usage...")

        # Get events from the last 7 days (to avoid overwhelming API calls)
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=7)

        paginator = cloudtrail.get_paginator('lookup_events')

        service_events = {}
        event_count = 0

        for page in paginator.paginate(
            StartTime=start_time,
            EndTime=end_time,
            PaginationConfig={'MaxItems': 1000, 'PageSize': 50}
        ):
            for event in page.get('Events', []):
                event_count += 1
                event_source = event.get('EventSource', '')

                if event_source:
                    # Convert event source to service name
                    service_name = event_source.replace('.amazonaws.com', '').replace('.', ' ').title()

                    if service_name not in service_events:
                        service_events[service_name] = {
                            'event_count': 0,
                            'first_seen': event.get('EventTime'),
                            'last_seen': event.get('EventTime')
                        }

                    service_events[service_name]['event_count'] += 1
                    service_events[service_name]['last_seen'] = event.get('EventTime')

        # Convert to service dictionary format
        for service_name, event_data in service_events.items():
            cloudtrail_services[service_name] = {
                'has_costs': False,  # Will be updated if found in cost data
                'source': 'CloudTrail Events',
                'event_count': event_data['event_count'],
                'first_seen': event_data['first_seen'].strftime('%Y-%m-%d %H:%M:%S') if event_data['first_seen'] else 'Unknown',
                'last_detected': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        utils.log_info(f"Analyzed {event_count} CloudTrail events, found {len(cloudtrail_services)} services")

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            utils.log_warning("Access denied to CloudTrail. Event history data will not be included.")
        else:
            utils.log_warning(f"Error accessing CloudTrail: {e}")
    except Exception as e:
        utils.log_warning(f"Error getting CloudTrail data: {e}")

    return cloudtrail_services

def consolidate_service_data(cost_services, enumerated_services, cloudtrail_services):
    """
    Consolidate service data from all discovery methods.

    Args:
        cost_services: Services found in Cost Explorer
        enumerated_services: Services found by resource enumeration
        cloudtrail_services: Services found in CloudTrail events

    Returns:
        dict: Consolidated service data
    """
    consolidated = {}

    # Start with cost services (these definitely have costs)
    for service_name, service_data in cost_services.items():
        consolidated[service_name] = service_data.copy()
        consolidated[service_name]['detection_methods'] = ['Cost Explorer']

    # Add enumerated services
    for service_name, service_data in enumerated_services.items():
        if service_name in consolidated:
            # Merge data
            consolidated[service_name]['detection_methods'].append('Resource Enumeration')
            if 'regions' in service_data:
                consolidated[service_name]['regions'] = service_data['regions']
        else:
            consolidated[service_name] = service_data.copy()
            consolidated[service_name]['detection_methods'] = ['Resource Enumeration']

    # Add CloudTrail services
    for service_name, service_data in cloudtrail_services.items():
        if service_name in consolidated:
            # Merge data
            consolidated[service_name]['detection_methods'].append('CloudTrail Events')
            if 'event_count' in service_data:
                consolidated[service_name]['event_count'] = service_data['event_count']
                consolidated[service_name]['first_seen'] = service_data['first_seen']
        else:
            consolidated[service_name] = service_data.copy()
            consolidated[service_name]['detection_methods'] = ['CloudTrail Events']

    # Update has_costs flag for services found in cost data
    for service_name in consolidated:
        if service_name in cost_services:
            consolidated[service_name]['has_costs'] = True

    return consolidated

def export_to_excel(services_data, account_id, account_name):
    """
    Export services data to Excel file with AWS naming convention.

    Args:
        services_data: Dictionary of consolidated service data
        account_id: AWS account ID
        account_name: AWS account name

    Returns:
        str: Filename of exported file or None if failed
    """
    if not services_data:
        utils.log_warning("No services data to export.")
        return None

    try:
        # Import pandas after dependency check
        import pandas as pd

        # Generate filename with AWS identifier
        current_date = datetime.datetime.now().strftime("%m.%d.%Y")

        # Use utils module to generate filename and save data with AWS identifier
        filename = utils.create_export_filename(
            account_name,
            "services-in-use",
            "",
            current_date
        )

        # Prepare data for export
        export_data = []
        for service_name, service_info in services_data.items():
            row = {
                'Service Name': service_name,
                'Has Costs': 'Yes' if service_info.get('has_costs', False) else 'No',
                'Detection Methods': ', '.join(service_info.get('detection_methods', [])),
                'Regions': ', '.join(service_info.get('regions', ['N/A'])),
                'Event Count (7 days)': service_info.get('event_count', 'N/A'),
                'First Seen': service_info.get('first_seen', 'N/A'),
                'Last Detected': service_info.get('last_detected', 'N/A'),
                'Source': service_info.get('source', 'Multiple')
            }
            export_data.append(row)

        # Sort by service name
        export_data.sort(key=lambda x: x['Service Name'])

        # Create DataFrame
        services_df = pd.DataFrame(export_data)

        # Create summary data
        total_services = len(services_data)
        services_with_costs = len([s for s in services_data.values() if s.get('has_costs', False)])
        services_without_costs = total_services - services_with_costs

        detection_methods = {}
        for service_info in services_data.values():
            for method in service_info.get('detection_methods', []):
                detection_methods[method] = detection_methods.get(method, 0) + 1

        summary_data = {
            'Metric': [
                'Total Services Detected',
                'Services with Costs',
                'Services without Costs',
                'Detected via Cost Explorer',
                'Detected via Resource Enumeration',
                'Detected via CloudTrail Events',
                'Multi-Method Detection'
            ],
            'Count': [
                total_services,
                services_with_costs,
                services_without_costs,
                detection_methods.get('Cost Explorer', 0),
                detection_methods.get('Resource Enumeration', 0),
                detection_methods.get('CloudTrail Events', 0),
                len([s for s in services_data.values() if len(s.get('detection_methods', [])) > 1])
            ]
        }

        summary_df = pd.DataFrame(summary_data)

        # Prepare data frames for multi-sheet export
        data_frames = {
            'Services Summary': summary_df,
            'Services Details': services_df
        }

        # Save using utils function for multi-sheet Excel
        output_path = utils.save_multiple_dataframes_to_excel(data_frames, filename)

        if output_path:
            utils.log_success("AWS services in use data exported successfully!")
            utils.log_info(f"File location: {output_path}")
            utils.log_info(f"Export contains {total_services} services ({services_with_costs} with costs, {services_without_costs} without costs)")
            return str(output_path)
        else:
            utils.log_error("Error exporting to Excel. Please check the logs.")
            return None

    except Exception as e:
        utils.log_error("Error exporting to Excel", e)
        return None

def main():
    """
    Main function to orchestrate the services discovery.
    """
    start_time = datetime.datetime.now()
    script_name = "services-in-use-export.py"

    try:
        # Log script start
        utils.log_script_start(script_name, "AWS Services Discovery and Export")

        # Check dependencies first
        utils.log_section("DEPENDENCY CHECK")
        if not check_dependencies():
            utils.log_error("Dependency check failed")
            return

        # Import pandas after dependency check
        import pandas as pd

        # Print title and get account info
        account_id, account_name = print_title()

        try:
            # Test AWS credentials
            sts = utils.get_boto3_client('sts')
            sts.get_caller_identity()
            utils.log_success("AWS credentials validated")

        except NoCredentialsError:
            utils.log_error("AWS credentials not found. Please configure your credentials using:")
            print("  - AWS CLI: aws configure")
            print("  - Environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            print("  - IAM role (if running on EC2)")
            return
        except Exception as e:
            utils.log_error("Error validating AWS credentials", e)
            return

        utils.log_info("Starting AWS services discovery from AWS...")
        print("====================================================================")

        # Discover services using multiple methods
        utils.log_info("Method 1: Analyzing Cost Explorer for services with billing activity...")
        cost_services = get_services_from_cost_explorer()

        utils.log_info("Method 2: Enumerating resources across major AWS services...")
        enumerated_services = discover_services_by_resource_enumeration()

        utils.log_info("Method 3: Analyzing CloudTrail events for service usage...")
        cloudtrail_services = get_services_from_cloudtrail()

        # Consolidate all service data
        utils.log_info("Consolidating service data from all discovery methods...")
        consolidated_services = consolidate_service_data(cost_services, enumerated_services, cloudtrail_services)

        if not consolidated_services:
            utils.log_warning("No services discovered. This may indicate permission issues or truly empty account.")
            return

        print("\n====================================================================")
        print("DISCOVERY COMPLETE")
        print("====================================================================")

        # Export to Excel
        filename = export_to_excel(consolidated_services, account_id, account_name)

        if filename:
            utils.log_info(f"Results exported with AWS compliance markers")
            utils.log_info(f"Total services discovered: {len(consolidated_services)}")

            # Display summary statistics
            services_with_costs = len([s for s in consolidated_services.values() if s.get('has_costs', False)])
            services_without_costs = len(consolidated_services) - services_with_costs

            utils.log_info(f"Services with costs: {services_with_costs}")
            utils.log_info(f"Services without costs: {services_without_costs}")

            # Show discovery method breakdown
            method_counts = {}
            for service_info in consolidated_services.values():
                for method in service_info.get('detection_methods', []):
                    method_counts[method] = method_counts.get(method, 0) + 1

            utils.log_info("Discovery method breakdown:")
            for method, count in method_counts.items():
                utils.log_info(f"  - {method}: {count} services")

            print("\nScript execution completed.")
        else:
            utils.log_error("Export failed. Please check the logs.")

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        utils.log_info("Script cancelled by user")
        sys.exit(0)
    except Exception as e:
        utils.log_error("Unexpected error occurred", e)
        sys.exit(1)
    finally:
        # Log script completion
        utils.log_script_end(script_name, start_time)

if __name__ == "__main__":
    main()