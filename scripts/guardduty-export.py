#!/usr/bin/env python3
"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS GuardDuty Export Tool
Version: v1.0.0
Date: NOV-09-2025

Description:
This script exports AWS GuardDuty threat detection information from all regions into an
Excel file with multiple worksheets. The output includes detectors, findings, threat
intelligence sets, IP sets, and publishing destinations.

Features:
- GuardDuty detectors with status and configuration
- Security findings with severity and threat details
- Threat intelligence sets (custom threat lists)
- IP sets for trusted/threat IPs
- Publishing destinations for findings
- Member accounts in multi-account setups
- Finding statistics and summaries
"""

import sys
import datetime
from pathlib import Path
from typing import List, Dict, Any

# Add path to import utils module
try:
    import utils
except ImportError:
    script_dir = Path(__file__).parent.absolute()

    if script_dir.name.lower() == 'scripts':
        sys.path.append(str(script_dir.parent))
    else:
        sys.path.append(str(script_dir))

    try:
        import utils
    except ImportError:
        print("ERROR: Could not import the utils module. Make sure utils.py is in the StratusScan directory.")
        sys.exit(1)

# Initialize logging
SCRIPT_START_TIME = datetime.datetime.now()
utils.setup_logging("guardduty-export")
utils.log_script_start("guardduty-export.py", "AWS GuardDuty Export Tool")


def print_title():
    """Print the title and header of the script to the console."""
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                    ")
    print("====================================================================")
    print("               AWS GUARDDUTY EXPORT TOOL")
    print("====================================================================")
    print("Version: v1.0.0                        Date: NOV-09-2025")
    print("Environment: AWS Commercial")
    print("====================================================================")

    # Get the current AWS account ID
    try:
        sts_client = utils.get_boto3_client('sts')
        account_id = sts_client.get_caller_identity().get('Account')
        account_name = utils.get_account_name(account_id, default=account_id)

        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
    except Exception as e:
        print("Could not determine account information.")
        utils.log_error("Error getting account information", e)
        account_id = "unknown"
        account_name = "unknown"

    print("====================================================================")
    return account_id, account_name


def get_aws_regions():
    """Get a list of available AWS regions."""
    try:
        regions = utils.get_available_aws_regions()
        if not regions:
            utils.log_warning("No accessible AWS regions found. Using default list.")
            regions = utils.get_default_regions()
        return regions
    except Exception as e:
        utils.log_error("Error getting AWS regions", e)
        return utils.get_default_regions()


@utils.aws_error_handler("Collecting GuardDuty detectors", default_return=[])
def collect_detectors(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect GuardDuty detector information from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with detector information
    """
    print("\n=== COLLECTING GUARDDUTY DETECTORS ===")
    all_detectors = []

    for region in regions:
        if not utils.validate_aws_region(region):
            utils.log_error(f"Skipping invalid AWS region: {region}")
            continue

        print(f"\nProcessing region: {region}")

        try:
            gd_client = utils.get_boto3_client('guardduty', region_name=region)

            # List detectors
            detector_response = gd_client.list_detectors()
            detector_ids = detector_response.get('DetectorIds', [])

            if not detector_ids:
                print(f"  No GuardDuty detector found in {region}")
                continue

            for detector_id in detector_ids:
                print(f"  Processing detector: {detector_id}")

                try:
                    # Get detector details
                    detector = gd_client.get_detector(DetectorId=detector_id)

                    # Status
                    status = detector.get('Status', '')

                    # Service role
                    service_role = detector.get('ServiceRole', 'N/A')

                    # Data sources
                    data_sources = detector.get('DataSources', {})
                    cloud_trail = data_sources.get('CloudTrail', {}).get('Status', 'N/A')
                    dns_logs = data_sources.get('DNSLogs', {}).get('Status', 'N/A')
                    flow_logs = data_sources.get('FlowLogs', {}).get('Status', 'N/A')
                    s3_logs = data_sources.get('S3Logs', {}).get('Status', 'N/A')
                    kubernetes = data_sources.get('Kubernetes', {})
                    k8s_audit_logs = kubernetes.get('AuditLogs', {}).get('Status', 'N/A') if kubernetes else 'N/A'

                    # Finding publishing frequency
                    finding_frequency = detector.get('FindingPublishingFrequency', 'N/A')

                    # Created at
                    created_at = detector.get('CreatedAt', '')
                    if created_at:
                        created_at = created_at if isinstance(created_at, str) else created_at.strftime('%Y-%m-%d %H:%M:%S')

                    # Updated at
                    updated_at = detector.get('UpdatedAt', '')
                    if updated_at:
                        updated_at = updated_at if isinstance(updated_at, str) else updated_at.strftime('%Y-%m-%d %H:%M:%S')

                    # Tags
                    tags = detector.get('Tags', {})
                    tags_str = ', '.join([f"{k}={v}" for k, v in tags.items()]) if tags else 'N/A'

                    all_detectors.append({
                        'Region': region,
                        'Detector ID': detector_id,
                        'Status': status,
                        'Finding Frequency': finding_frequency,
                        'CloudTrail': cloud_trail,
                        'DNS Logs': dns_logs,
                        'VPC Flow Logs': flow_logs,
                        'S3 Logs': s3_logs,
                        'Kubernetes Audit Logs': k8s_audit_logs,
                        'Service Role': service_role,
                        'Created At': created_at,
                        'Updated At': updated_at,
                        'Tags': tags_str
                    })

                except Exception as e:
                    utils.log_warning(f"Could not get details for detector {detector_id}: {e}")

        except Exception as e:
            utils.log_error(f"Error processing region {region} for GuardDuty detectors", e)

    utils.log_success(f"Total GuardDuty detectors collected: {len(all_detectors)}")
    return all_detectors


@utils.aws_error_handler("Collecting GuardDuty findings", default_return=[])
def collect_findings(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect GuardDuty findings from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with finding information
    """
    print("\n=== COLLECTING GUARDDUTY FINDINGS ===")
    all_findings = []

    for region in regions:
        if not utils.validate_aws_region(region):
            continue

        print(f"\nProcessing region: {region}")

        try:
            gd_client = utils.get_boto3_client('guardduty', region_name=region)

            # Get detectors first
            detector_response = gd_client.list_detectors()
            detector_ids = detector_response.get('DetectorIds', [])

            for detector_id in detector_ids:
                try:
                    # List findings
                    finding_paginator = gd_client.get_paginator('list_findings')

                    finding_ids = []
                    for finding_page in finding_paginator.paginate(DetectorId=detector_id):
                        finding_ids.extend(finding_page.get('FindingIds', []))

                    # Get finding details in batches (max 50 at a time)
                    for i in range(0, len(finding_ids), 50):
                        batch_ids = finding_ids[i:i+50]

                        findings_response = gd_client.get_findings(
                            DetectorId=detector_id,
                            FindingIds=batch_ids
                        )

                        findings = findings_response.get('Findings', [])

                        for finding in findings:
                            finding_id = finding.get('Id', '')
                            finding_type = finding.get('Type', '')
                            severity = finding.get('Severity', 0)

                            # Resource
                            resource = finding.get('Resource', {})
                            resource_type = resource.get('ResourceType', '')

                            # Instance details
                            instance_details = resource.get('InstanceDetails', {})
                            instance_id = instance_details.get('InstanceId', 'N/A')

                            # S3 bucket details
                            s3_details = resource.get('S3BucketDetails', [])
                            bucket_name = s3_details[0].get('Name', 'N/A') if s3_details else 'N/A'

                            # Title and description
                            title = finding.get('Title', '')
                            description = finding.get('Description', '')

                            # Service
                            service = finding.get('Service', {})
                            action = service.get('Action', {})
                            action_type = action.get('ActionType', 'N/A')

                            # Count
                            count = service.get('Count', 0)

                            # First seen
                            first_seen = service.get('EventFirstSeen', '')
                            if first_seen:
                                first_seen = first_seen if isinstance(first_seen, str) else first_seen.strftime('%Y-%m-%d %H:%M:%S')

                            # Last seen
                            last_seen = service.get('EventLastSeen', '')
                            if last_seen:
                                last_seen = last_seen if isinstance(last_seen, str) else last_seen.strftime('%Y-%m-%d %H:%M:%S')

                            # Created at
                            created_at = finding.get('CreatedAt', '')
                            if created_at:
                                created_at = created_at if isinstance(created_at, str) else created_at.strftime('%Y-%m-%d %H:%M:%S')

                            # Updated at
                            updated_at = finding.get('UpdatedAt', '')
                            if updated_at:
                                updated_at = updated_at if isinstance(updated_at, str) else updated_at.strftime('%Y-%m-%d %H:%M:%S')

                            all_findings.append({
                                'Region': region,
                                'Finding ID': finding_id,
                                'Type': finding_type,
                                'Severity': severity,
                                'Title': title,
                                'Description': description[:200] + '...' if len(description) > 200 else description,
                                'Resource Type': resource_type,
                                'Instance ID': instance_id,
                                'S3 Bucket': bucket_name,
                                'Action Type': action_type,
                                'Count': count,
                                'First Seen': first_seen,
                                'Last Seen': last_seen,
                                'Created At': created_at,
                                'Updated At': updated_at
                            })

                except Exception as e:
                    utils.log_warning(f"Could not get findings for detector {detector_id}: {e}")

        except Exception as e:
            utils.log_error(f"Error collecting findings in region {region}", e)

    utils.log_success(f"Total GuardDuty findings collected: {len(all_findings)}")
    return all_findings


@utils.aws_error_handler("Collecting threat intel sets", default_return=[])
def collect_threat_intel_sets(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect GuardDuty threat intelligence sets from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with threat intel set information
    """
    print("\n=== COLLECTING THREAT INTEL SETS ===")
    all_threat_sets = []

    for region in regions:
        if not utils.validate_aws_region(region):
            continue

        print(f"\nProcessing region: {region}")

        try:
            gd_client = utils.get_boto3_client('guardduty', region_name=region)

            # Get detectors first
            detector_response = gd_client.list_detectors()
            detector_ids = detector_response.get('DetectorIds', [])

            for detector_id in detector_ids:
                try:
                    # List threat intel sets
                    threat_set_paginator = gd_client.get_paginator('list_threat_intel_sets')

                    for threat_page in threat_set_paginator.paginate(DetectorId=detector_id):
                        threat_set_ids = threat_page.get('ThreatIntelSetIds', [])

                        for threat_set_id in threat_set_ids:
                            try:
                                # Get threat intel set details
                                threat_set = gd_client.get_threat_intel_set(
                                    DetectorId=detector_id,
                                    ThreatIntelSetId=threat_set_id
                                )

                                name = threat_set.get('Name', '')
                                format_type = threat_set.get('Format', '')
                                location = threat_set.get('Location', '')
                                status = threat_set.get('Status', '')

                                # Tags
                                tags = threat_set.get('Tags', {})
                                tags_str = ', '.join([f"{k}={v}" for k, v in tags.items()]) if tags else 'N/A'

                                all_threat_sets.append({
                                    'Region': region,
                                    'Detector ID': detector_id,
                                    'Threat Intel Set ID': threat_set_id,
                                    'Name': name,
                                    'Format': format_type,
                                    'Status': status,
                                    'Location': location,
                                    'Tags': tags_str
                                })

                            except Exception as e:
                                utils.log_warning(f"Could not get threat intel set {threat_set_id}: {e}")

                except Exception as e:
                    utils.log_warning(f"Could not get threat intel sets for detector {detector_id}: {e}")

        except Exception as e:
            utils.log_error(f"Error collecting threat intel sets in region {region}", e)

    utils.log_success(f"Total threat intel sets collected: {len(all_threat_sets)}")
    return all_threat_sets


@utils.aws_error_handler("Collecting IP sets", default_return=[])
def collect_ip_sets(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect GuardDuty IP sets from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with IP set information
    """
    print("\n=== COLLECTING IP SETS ===")
    all_ip_sets = []

    for region in regions:
        if not utils.validate_aws_region(region):
            continue

        print(f"\nProcessing region: {region}")

        try:
            gd_client = utils.get_boto3_client('guardduty', region_name=region)

            # Get detectors first
            detector_response = gd_client.list_detectors()
            detector_ids = detector_response.get('DetectorIds', [])

            for detector_id in detector_ids:
                try:
                    # List IP sets
                    ip_set_paginator = gd_client.get_paginator('list_ip_sets')

                    for ip_page in ip_set_paginator.paginate(DetectorId=detector_id):
                        ip_set_ids = ip_page.get('IpSetIds', [])

                        for ip_set_id in ip_set_ids:
                            try:
                                # Get IP set details
                                ip_set = gd_client.get_ip_set(
                                    DetectorId=detector_id,
                                    IpSetId=ip_set_id
                                )

                                name = ip_set.get('Name', '')
                                format_type = ip_set.get('Format', '')
                                location = ip_set.get('Location', '')
                                status = ip_set.get('Status', '')

                                # Tags
                                tags = ip_set.get('Tags', {})
                                tags_str = ', '.join([f"{k}={v}" for k, v in tags.items()]) if tags else 'N/A'

                                all_ip_sets.append({
                                    'Region': region,
                                    'Detector ID': detector_id,
                                    'IP Set ID': ip_set_id,
                                    'Name': name,
                                    'Format': format_type,
                                    'Status': status,
                                    'Location': location,
                                    'Tags': tags_str
                                })

                            except Exception as e:
                                utils.log_warning(f"Could not get IP set {ip_set_id}: {e}")

                except Exception as e:
                    utils.log_warning(f"Could not get IP sets for detector {detector_id}: {e}")

        except Exception as e:
            utils.log_error(f"Error collecting IP sets in region {region}", e)

    utils.log_success(f"Total IP sets collected: {len(all_ip_sets)}")
    return all_ip_sets


def export_guardduty_data(account_id: str, account_name: str):
    """
    Export GuardDuty information to an Excel file.

    Args:
        account_id: The AWS account ID
        account_name: The AWS account name
    """
    # Ask for region selection
    print("\n" + "=" * 60)
    print("AWS Region Selection:")
    print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1")
    region_input = input("Would you like all AWS regions (type \"all\") or a specific region (ex. \"us-east-1\")? ").strip().lower()

    # Get all available AWS regions
    all_available_regions = get_aws_regions()

    # Determine regions to scan
    if region_input == "all":
        regions = all_available_regions
        region_text = "all AWS regions"
        region_suffix = ""
    else:
        # Validate the provided region
        if utils.validate_aws_region(region_input):
            regions = [region_input]
            region_text = f"AWS region {region_input}"
            region_suffix = f"-{region_input}"
        else:
            utils.log_warning(f"'{region_input}' is not a valid AWS region. Using all AWS regions.")
            regions = all_available_regions
            region_text = "all AWS regions"
            region_suffix = ""

    print(f"\nStarting GuardDuty export process for {region_text}...")
    print("This may take some time depending on the number of regions and resources...")

    utils.log_info(f"Processing {len(regions)} AWS regions: {', '.join(regions)}")

    # Import pandas for DataFrame handling
    import pandas as pd

    # Dictionary to hold all DataFrames for export
    data_frames = {}

    # STEP 1: Collect detectors
    detectors = collect_detectors(regions)
    if detectors:
        data_frames['Detectors'] = pd.DataFrame(detectors)

    # STEP 2: Collect findings
    findings = collect_findings(regions)
    if findings:
        data_frames['Findings'] = pd.DataFrame(findings)

    # STEP 3: Collect threat intel sets
    threat_sets = collect_threat_intel_sets(regions)
    if threat_sets:
        data_frames['Threat Intel Sets'] = pd.DataFrame(threat_sets)

    # STEP 4: Collect IP sets
    ip_sets = collect_ip_sets(regions)
    if ip_sets:
        data_frames['IP Sets'] = pd.DataFrame(ip_sets)

    # Check if we have any data
    if not data_frames:
        utils.log_warning("No GuardDuty data was collected. Nothing to export.")
        print("\nNo GuardDuty detectors found in the selected region(s).")
        return

    # STEP 5: Prepare all DataFrames for export
    for sheet_name in data_frames:
        data_frames[sheet_name] = utils.prepare_dataframe_for_export(data_frames[sheet_name])

    # STEP 6: Create filename and export
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    final_excel_file = utils.create_export_filename(
        account_name,
        'guardduty',
        region_suffix,
        current_date
    )

    # Save using utils module for consistent formatting
    try:
        output_path = utils.save_multiple_dataframes_to_excel(data_frames, final_excel_file)

        if output_path:
            utils.log_success("GuardDuty data exported successfully!")
            utils.log_info(f"File location: {output_path}")
            utils.log_info(f"Export contains data from {len(regions)} AWS region(s)")

            # Summary of exported data
            for sheet_name, df in data_frames.items():
                utils.log_info(f"  - {sheet_name}: {len(df)} records")
                print(f"  - {sheet_name}: {len(df)} records")
        else:
            utils.log_error("Error creating Excel file. Please check the logs.")

    except Exception as e:
        utils.log_error("Error creating Excel file", e)


def main():
    """Main function to execute the script."""
    try:
        # Print title and get account information
        account_id, account_name = print_title()

        # Check and install dependencies
        if not utils.ensure_dependencies('pandas', 'openpyxl'):
            sys.exit(1)

        # Check if account name is unknown
        if account_name == "unknown":
            proceed = input("Unable to determine account name. Proceed anyway? (y/n): ").lower()
            if proceed != 'y':
                print("Exiting script...")
                sys.exit(0)

        # Export GuardDuty data
        export_guardduty_data(account_id, account_name)

        print("\nGuardDuty export script execution completed.")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        utils.log_info("Script cancelled by user")
        sys.exit(1)
    except Exception as e:
        utils.log_error("An unexpected error occurred", e)
        sys.exit(1)
    finally:
        utils.log_script_end("guardduty-export.py", SCRIPT_START_TIME)


if __name__ == "__main__":
    main()
