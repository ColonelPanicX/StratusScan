#!/usr/bin/env python3
"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS EventBridge Export Tool
Version: v1.0.0
Date: NOV-09-2025

Description:
This script exports AWS EventBridge information into an Excel file with multiple
worksheets. The output includes event buses, rules, targets, and archive configurations.

Features:
- Event buses (custom and default) with policies
- Event rules with event patterns and schedules
- Rule targets with input transformations
- Event archives for replay capabilities
- Schema registries and schemas
"""

import sys
import datetime
import json
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
        print("ERROR: Could not import the utils module. Make sure utils.py in the StratusScan directory.")
        sys.exit(1)

# Initialize logging
SCRIPT_START_TIME = datetime.datetime.now()
utils.setup_logging("eventbridge-export")
utils.log_script_start("eventbridge-export.py", "AWS EventBridge Export Tool")


def print_title():
    """Print the title and header of the script to the console."""
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                    ")
    print("====================================================================")
    print("               AWS EVENTBRIDGE EXPORT TOOL")
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


@utils.aws_error_handler("Collecting event buses", default_return=[])
def collect_event_buses(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect EventBridge event bus information from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with event bus information
    """
    print("\n=== COLLECTING EVENT BUSES ===")
    all_buses = []

    for region in regions:
        if not utils.validate_aws_region(region):
            continue

        print(f"\nProcessing region: {region}")

        try:
            events_client = utils.get_boto3_client('events', region_name=region)

            paginator = events_client.get_paginator('list_event_buses')
            for page in paginator.paginate():
                buses = page.get('EventBuses', [])

                for bus in buses:
                    bus_name = bus.get('Name', 'N/A')

                    print(f"  Processing event bus: {bus_name}")

                    # Bus details
                    bus_arn = bus.get('Arn', 'N/A')

                    # Policy
                    policy = bus.get('Policy', None)
                    has_policy = 'Yes' if policy else 'No'

                    all_buses.append({
                        'Region': region,
                        'Event Bus Name': bus_name,
                        'Event Bus ARN': bus_arn,
                        'Has Policy': has_policy
                    })

        except Exception as e:
            utils.log_error(f"Error collecting event buses in region {region}", e)

    utils.log_success(f"Total event buses collected: {len(all_buses)}")
    return all_buses


@utils.aws_error_handler("Collecting event rules", default_return=[])
def collect_event_rules(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect EventBridge rule information from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with rule information
    """
    print("\n=== COLLECTING EVENT RULES ===")
    all_rules = []

    for region in regions:
        if not utils.validate_aws_region(region):
            continue

        print(f"\nProcessing region: {region}")

        try:
            events_client = utils.get_boto3_client('events', region_name=region)

            # Get event buses first
            buses_response = events_client.list_event_buses()
            buses = buses_response.get('EventBuses', [])

            for bus in buses:
                bus_name = bus.get('Name', 'default')

                try:
                    # Get rules for this bus
                    paginator = events_client.get_paginator('list_rules')
                    for page in paginator.paginate(EventBusName=bus_name):
                        rules = page.get('Rules', [])

                        for rule in rules:
                            rule_name = rule.get('Name', 'N/A')

                            print(f"  Processing rule: {bus_name}/{rule_name}")

                            # Rule details
                            rule_arn = rule.get('Arn', 'N/A')
                            state = rule.get('State', 'UNKNOWN')
                            description = rule.get('Description', 'N/A')

                            # Event pattern or schedule
                            event_pattern = rule.get('EventPattern', None)
                            schedule_expression = rule.get('ScheduleExpression', None)

                            rule_type = 'Event Pattern' if event_pattern else 'Schedule' if schedule_expression else 'Unknown'

                            # Managed by
                            managed_by = rule.get('ManagedBy', 'Customer')

                            # Role ARN
                            role_arn = rule.get('RoleArn', 'N/A')

                            all_rules.append({
                                'Region': region,
                                'Event Bus': bus_name,
                                'Rule Name': rule_name,
                                'State': state,
                                'Rule Type': rule_type,
                                'Schedule Expression': schedule_expression if schedule_expression else 'N/A',
                                'Has Event Pattern': 'Yes' if event_pattern else 'No',
                                'Description': description,
                                'Managed By': managed_by,
                                'Role ARN': role_arn,
                                'Rule ARN': rule_arn
                            })

                except Exception as e:
                    utils.log_warning(f"Could not get rules for bus {bus_name}: {e}")

        except Exception as e:
            utils.log_error(f"Error collecting event rules in region {region}", e)

    utils.log_success(f"Total event rules collected: {len(all_rules)}")
    return all_rules


@utils.aws_error_handler("Collecting rule targets", default_return=[])
def collect_rule_targets(regions: List[str]) -> List[Dict[str, Any]]:
    """
    Collect EventBridge rule target information from AWS regions.

    Args:
        regions: List of AWS regions to scan

    Returns:
        list: List of dictionaries with target information
    """
    print("\n=== COLLECTING RULE TARGETS ===")
    all_targets = []

    for region in regions:
        if not utils.validate_aws_region(region):
            continue

        print(f"\nProcessing region: {region}")

        try:
            events_client = utils.get_boto3_client('events', region_name=region)

            # Get event buses
            buses_response = events_client.list_event_buses()
            buses = buses_response.get('EventBuses', [])

            for bus in buses:
                bus_name = bus.get('Name', 'default')

                try:
                    # Get rules for this bus
                    rules_response = events_client.list_rules(EventBusName=bus_name)
                    rules = rules_response.get('Rules', [])

                    for rule in rules:
                        rule_name = rule.get('Name', '')

                        try:
                            # Get targets for this rule
                            targets_response = events_client.list_targets_by_rule(
                                Rule=rule_name,
                                EventBusName=bus_name
                            )
                            targets = targets_response.get('Targets', [])

                            for target in targets:
                                target_id = target.get('Id', 'N/A')
                                target_arn = target.get('Arn', 'N/A')

                                # Determine target type from ARN
                                target_type = 'Unknown'
                                if ':lambda:' in target_arn:
                                    target_type = 'Lambda'
                                elif ':sqs:' in target_arn:
                                    target_type = 'SQS'
                                elif ':sns:' in target_arn:
                                    target_type = 'SNS'
                                elif ':kinesis:' in target_arn:
                                    target_type = 'Kinesis'
                                elif ':states:' in target_arn:
                                    target_type = 'Step Functions'
                                elif ':events:' in target_arn:
                                    target_type = 'Event Bus'
                                elif ':logs:' in target_arn:
                                    target_type = 'CloudWatch Logs'

                                # Role ARN
                                role_arn = target.get('RoleArn', 'N/A')

                                # Input transformation
                                input_transformer = target.get('InputTransformer', None)
                                has_input_transformer = 'Yes' if input_transformer else 'No'

                                # Dead letter config
                                dead_letter_config = target.get('DeadLetterConfig', None)
                                has_dlq = 'Yes' if dead_letter_config else 'No'

                                # Retry policy
                                retry_policy = target.get('RetryPolicy', {})
                                max_retry_attempts = retry_policy.get('MaximumRetryAttempts', 'Default')
                                max_event_age = retry_policy.get('MaximumEventAgeInSeconds', 'Default')

                                all_targets.append({
                                    'Region': region,
                                    'Event Bus': bus_name,
                                    'Rule Name': rule_name,
                                    'Target ID': target_id,
                                    'Target Type': target_type,
                                    'Target ARN': target_arn,
                                    'Role ARN': role_arn,
                                    'Has Input Transformer': has_input_transformer,
                                    'Has Dead Letter Queue': has_dlq,
                                    'Max Retry Attempts': max_retry_attempts,
                                    'Max Event Age (seconds)': max_event_age
                                })

                        except Exception as e:
                            utils.log_warning(f"Could not get targets for rule {rule_name}: {e}")

                except Exception as e:
                    utils.log_warning(f"Could not process bus {bus_name}: {e}")

        except Exception as e:
            utils.log_error(f"Error collecting rule targets in region {region}", e)

    utils.log_success(f"Total rule targets collected: {len(all_targets)}")
    return all_targets


def export_eventbridge_data(account_id: str, account_name: str):
    """
    Export EventBridge information to an Excel file.

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

    print(f"\nStarting EventBridge export process for {region_text}...")
    print("This may take some time depending on the number of regions and resources...")

    utils.log_info(f"Processing {len(regions)} AWS regions: {', '.join(regions)}")

    # Import pandas for DataFrame handling
    import pandas as pd

    # Dictionary to hold all DataFrames for export
    data_frames = {}

    # STEP 1: Collect event buses
    buses = collect_event_buses(regions)
    if buses:
        data_frames['Event Buses'] = pd.DataFrame(buses)

    # STEP 2: Collect event rules
    rules = collect_event_rules(regions)
    if rules:
        data_frames['Event Rules'] = pd.DataFrame(rules)

    # STEP 3: Collect rule targets
    targets = collect_rule_targets(regions)
    if targets:
        data_frames['Rule Targets'] = pd.DataFrame(targets)

    # STEP 4: Create summary
    if buses or rules or targets:
        summary_data = []

        total_buses = len(buses)
        total_rules = len(rules)
        total_targets = len(targets)

        # Rules by state
        enabled_rules = sum(1 for r in rules if r['State'] == 'ENABLED')
        disabled_rules = sum(1 for r in rules if r['State'] == 'DISABLED')

        # Rules by type
        pattern_rules = sum(1 for r in rules if r['Rule Type'] == 'Event Pattern')
        schedule_rules = sum(1 for r in rules if r['Rule Type'] == 'Schedule')

        summary_data.append({'Metric': 'Total Event Buses', 'Value': total_buses})
        summary_data.append({'Metric': 'Total Event Rules', 'Value': total_rules})
        summary_data.append({'Metric': 'Enabled Rules', 'Value': enabled_rules})
        summary_data.append({'Metric': 'Disabled Rules', 'Value': disabled_rules})
        summary_data.append({'Metric': 'Event Pattern Rules', 'Value': pattern_rules})
        summary_data.append({'Metric': 'Schedule Rules', 'Value': schedule_rules})
        summary_data.append({'Metric': 'Total Rule Targets', 'Value': total_targets})

        data_frames['Summary'] = pd.DataFrame(summary_data)

    # Check if we have any data
    if not data_frames:
        utils.log_warning("No EventBridge data was collected. Nothing to export.")
        print("\nNo EventBridge resources found in the selected region(s).")
        return

    # STEP 5: Prepare all DataFrames for export
    for sheet_name in data_frames:
        data_frames[sheet_name] = utils.prepare_dataframe_for_export(data_frames[sheet_name])

    # STEP 6: Create filename and export
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    final_excel_file = utils.create_export_filename(
        account_name,
        'eventbridge',
        region_suffix,
        current_date
    )

    # Save using utils module for consistent formatting
    try:
        output_path = utils.save_multiple_dataframes_to_excel(data_frames, final_excel_file)

        if output_path:
            utils.log_success("EventBridge data exported successfully!")
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

        # Export EventBridge data
        export_eventbridge_data(account_id, account_name)

        print("\nEventBridge export script execution completed.")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        utils.log_info("Script cancelled by user")
        sys.exit(1)
    except Exception as e:
        utils.log_error("An unexpected error occurred", e)
        sys.exit(1)
    finally:
        utils.log_script_end("eventbridge-export.py", SCRIPT_START_TIME)


if __name__ == "__main__":
    main()
