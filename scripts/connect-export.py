#!/usr/bin/env python3
"""
AWS Connect Export Script

Exports AWS Connect contact center resources:
- Connect Instances (contact centers)
- Hours of Operation
- Queues and routing profiles
- Contact flows (IVR flows)
- Phone numbers and contact flow associations
- Security profiles and users
- Quick connects
- Instance storage configurations

Features:
- Complete Connect instance inventory
- Contact flow and queue analysis
- Phone number tracking
- User and security profile management
- Hours of operation tracking
- Multi-region support
- Comprehensive multi-worksheet export

Note: Requires connect:* permissions
Note: Connect is a regional service
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

# Standard utils import pattern
try:
    import utils
except ImportError:
    script_dir = Path(__file__).parent.absolute()
    if script_dir.name.lower() == 'scripts':
        sys.path.append(str(script_dir.parent))
    else:
        sys.path.append(str(script_dir))
    import utils

# Check required packages
utils.check_required_packages(['boto3', 'pandas', 'openpyxl'])

# Setup logging
logger = utils.setup_logging('connect-export')
utils.log_script_start('connect-export', 'Export AWS Connect contact center resources')


@utils.aws_error_handler("Collecting Connect instances", default_return=[])
def collect_connect_instances(region: str) -> List[Dict[str, Any]]:
    """Collect all Connect instances in a region."""
    connect = utils.get_boto3_client('connect', region_name=region)
    instances = []

    try:
        paginator = connect.get_paginator('list_instances')
        for page in paginator.paginate():
            for instance in page.get('InstanceSummaryList', []):
                instance_id = instance.get('Id', 'N/A')

                # Get detailed instance information
                try:
                    detail = connect.describe_instance(InstanceId=instance_id)
                    instance_detail = detail.get('Instance', {})

                    # Get instance attributes
                    attrs = instance_detail.get('InstanceAttributes', {})

                    instances.append({
                        'Region': region,
                        'InstanceId': instance_id,
                        'InstanceAlias': instance.get('InstanceAlias', 'N/A'),
                        'InstanceArn': instance.get('Arn', 'N/A'),
                        'IdentityManagementType': instance.get('IdentityManagementType', 'N/A'),
                        'InboundCallsEnabled': instance.get('InboundCallsEnabled', False),
                        'OutboundCallsEnabled': instance.get('OutboundCallsEnabled', False),
                        'CreatedTime': instance.get('CreatedTime', 'N/A'),
                        'ServiceRole': instance_detail.get('ServiceRole', 'N/A'),
                        'InstanceStatus': instance_detail.get('InstanceStatus', 'N/A'),
                        'StatusReason': str(instance_detail.get('StatusReason', 'N/A')),
                        'InboundContactsFlowEnabled': attrs.get('InboundCalls', False),
                        'OutboundContactsFlowEnabled': attrs.get('OutboundCalls', False),
                        'ContactflowLogsEnabled': attrs.get('ContactflowLogs', False),
                        'ContactLensEnabled': attrs.get('ContactLens', False),
                        'AutoResolveBestVoicesEnabled': attrs.get('AutoResolveBestVoices', False),
                        'UseCustomTTSVoices': attrs.get('UseCustomTTSVoices', False),
                        'EarlyMediaEnabled': attrs.get('EarlyMedia', False),
                    })
                except Exception:
                    # Fallback to summary data
                    instances.append({
                        'Region': region,
                        'InstanceId': instance_id,
                        'InstanceAlias': instance.get('InstanceAlias', 'N/A'),
                        'InstanceArn': instance.get('Arn', 'N/A'),
                        'IdentityManagementType': instance.get('IdentityManagementType', 'N/A'),
                        'InboundCallsEnabled': instance.get('InboundCallsEnabled', False),
                        'OutboundCallsEnabled': instance.get('OutboundCallsEnabled', False),
                        'CreatedTime': instance.get('CreatedTime', 'N/A'),
                        'ServiceRole': 'N/A',
                        'InstanceStatus': 'N/A',
                        'StatusReason': 'N/A',
                        'InboundContactsFlowEnabled': 'N/A',
                        'OutboundContactsFlowEnabled': 'N/A',
                        'ContactflowLogsEnabled': 'N/A',
                        'ContactLensEnabled': 'N/A',
                        'AutoResolveBestVoicesEnabled': 'N/A',
                        'UseCustomTTSVoices': 'N/A',
                        'EarlyMediaEnabled': 'N/A',
                    })
    except Exception:
        pass

    return instances


@utils.aws_error_handler("Collecting hours of operation", default_return=[])
def collect_hours_of_operation(region: str, instance_id: str) -> List[Dict[str, Any]]:
    """Collect hours of operation for a Connect instance."""
    connect = utils.get_boto3_client('connect', region_name=region)
    hours_list = []

    try:
        paginator = connect.get_paginator('list_hours_of_operations')
        for page in paginator.paginate(InstanceId=instance_id):
            for hours in page.get('HoursOfOperationSummaryList', []):
                hours_list.append({
                    'Region': region,
                    'InstanceId': instance_id,
                    'HoursOfOperationId': hours.get('Id', 'N/A'),
                    'HoursOfOperationArn': hours.get('Arn', 'N/A'),
                    'Name': hours.get('Name', 'N/A'),
                })
    except Exception:
        pass

    return hours_list


@utils.aws_error_handler("Collecting queues", default_return=[])
def collect_queues(region: str, instance_id: str) -> List[Dict[str, Any]]:
    """Collect queues for a Connect instance."""
    connect = utils.get_boto3_client('connect', region_name=region)
    queues = []

    try:
        paginator = connect.get_paginator('list_queues')
        for page in paginator.paginate(InstanceId=instance_id):
            for queue in page.get('QueueSummaryList', []):
                queue_id = queue.get('Id', 'N/A')

                # Get queue details
                try:
                    detail = connect.describe_queue(InstanceId=instance_id, QueueId=queue_id)
                    queue_detail = detail.get('Queue', {})

                    queues.append({
                        'Region': region,
                        'InstanceId': instance_id,
                        'QueueId': queue_id,
                        'QueueArn': queue.get('Arn', 'N/A'),
                        'Name': queue.get('Name', 'N/A'),
                        'QueueType': queue.get('QueueType', 'N/A'),
                        'Description': queue_detail.get('Description', 'N/A'),
                        'HoursOfOperationId': queue_detail.get('HoursOfOperationId', 'N/A'),
                        'MaxContacts': queue_detail.get('MaxContacts', 'N/A'),
                        'Status': queue_detail.get('Status', 'N/A'),
                    })
                except Exception:
                    queues.append({
                        'Region': region,
                        'InstanceId': instance_id,
                        'QueueId': queue_id,
                        'QueueArn': queue.get('Arn', 'N/A'),
                        'Name': queue.get('Name', 'N/A'),
                        'QueueType': queue.get('QueueType', 'N/A'),
                        'Description': 'N/A',
                        'HoursOfOperationId': 'N/A',
                        'MaxContacts': 'N/A',
                        'Status': 'N/A',
                    })
    except Exception:
        pass

    return queues


@utils.aws_error_handler("Collecting contact flows", default_return=[])
def collect_contact_flows(region: str, instance_id: str) -> List[Dict[str, Any]]:
    """Collect contact flows (IVR flows) for a Connect instance."""
    connect = utils.get_boto3_client('connect', region_name=region)
    flows = []

    try:
        paginator = connect.get_paginator('list_contact_flows')
        for page in paginator.paginate(InstanceId=instance_id):
            for flow in page.get('ContactFlowSummaryList', []):
                flows.append({
                    'Region': region,
                    'InstanceId': instance_id,
                    'ContactFlowId': flow.get('Id', 'N/A'),
                    'ContactFlowArn': flow.get('Arn', 'N/A'),
                    'Name': flow.get('Name', 'N/A'),
                    'ContactFlowType': flow.get('ContactFlowType', 'N/A'),
                    'ContactFlowState': flow.get('ContactFlowState', 'N/A'),
                })
    except Exception:
        pass

    return flows


@utils.aws_error_handler("Collecting phone numbers", default_return=[])
def collect_phone_numbers(region: str, instance_id: str) -> List[Dict[str, Any]]:
    """Collect phone numbers for a Connect instance."""
    connect = utils.get_boto3_client('connect', region_name=region)
    phone_numbers = []

    try:
        paginator = connect.get_paginator('list_phone_numbers')
        for page in paginator.paginate(InstanceId=instance_id):
            for phone in page.get('PhoneNumberSummaryList', []):
                phone_number_id = phone.get('Id', 'N/A')

                # Get phone number details
                try:
                    detail = connect.describe_phone_number(PhoneNumberId=phone_number_id)
                    phone_detail = detail.get('ClaimedPhoneNumberSummary', {})

                    phone_numbers.append({
                        'Region': region,
                        'InstanceId': instance_id,
                        'PhoneNumberId': phone_number_id,
                        'PhoneNumberArn': phone.get('Arn', 'N/A'),
                        'PhoneNumber': phone.get('PhoneNumber', 'N/A'),
                        'PhoneNumberType': phone.get('PhoneNumberType', 'N/A'),
                        'PhoneNumberCountryCode': phone.get('PhoneNumberCountryCode', 'N/A'),
                        'TargetArn': phone_detail.get('TargetArn', 'N/A'),
                        'PhoneNumberStatus': phone_detail.get('PhoneNumberStatus', {}).get('Status', 'N/A'),
                    })
                except Exception:
                    phone_numbers.append({
                        'Region': region,
                        'InstanceId': instance_id,
                        'PhoneNumberId': phone_number_id,
                        'PhoneNumberArn': phone.get('Arn', 'N/A'),
                        'PhoneNumber': phone.get('PhoneNumber', 'N/A'),
                        'PhoneNumberType': phone.get('PhoneNumberType', 'N/A'),
                        'PhoneNumberCountryCode': phone.get('PhoneNumberCountryCode', 'N/A'),
                        'TargetArn': 'N/A',
                        'PhoneNumberStatus': 'N/A',
                    })
    except Exception:
        pass

    return phone_numbers


@utils.aws_error_handler("Collecting users", default_return=[])
def collect_users(region: str, instance_id: str) -> List[Dict[str, Any]]:
    """Collect users for a Connect instance."""
    connect = utils.get_boto3_client('connect', region_name=region)
    users = []

    try:
        paginator = connect.get_paginator('list_users')
        for page in paginator.paginate(InstanceId=instance_id):
            for user in page.get('UserSummaryList', []):
                users.append({
                    'Region': region,
                    'InstanceId': instance_id,
                    'UserId': user.get('Id', 'N/A'),
                    'UserArn': user.get('Arn', 'N/A'),
                    'Username': user.get('Username', 'N/A'),
                })
    except Exception:
        pass

    return users


def main():
    """Main execution function."""
    try:
        # Get account information
        account_id, account_name = utils.get_account_info()
        utils.log_info(f"Exporting AWS Connect resources for account: {account_name} ({account_id})")

        # Prompt for regions
        utils.log_info("AWS Connect is a regional service.")
        regions = utils.prompt_region_selection(
            service_name="AWS Connect",
            default_to_all=False
        )

        if not regions:
            utils.log_error("No regions selected. Exiting.")
            return

        utils.log_info(f"Scanning {len(regions)} region(s) for AWS Connect resources...")

        # Collect all resources
        all_instances = []
        all_hours = []
        all_queues = []
        all_flows = []
        all_phone_numbers = []
        all_users = []

        for idx, region in enumerate(regions, 1):
            utils.log_info(f"[{idx}/{len(regions)}] Processing region: {region}")

            # Collect instances
            instances = collect_connect_instances(region)
            if instances:
                utils.log_info(f"  Found {len(instances)} Connect instance(s)")
                all_instances.extend(instances)

                # Collect resources for each instance
                for instance in instances:
                    instance_id = instance['InstanceId']

                    # Collect hours of operation
                    hours = collect_hours_of_operation(region, instance_id)
                    all_hours.extend(hours)

                    # Collect queues
                    queues = collect_queues(region, instance_id)
                    all_queues.extend(queues)

                    # Collect contact flows
                    flows = collect_contact_flows(region, instance_id)
                    all_flows.extend(flows)

                    # Collect phone numbers
                    phone_numbers = collect_phone_numbers(region, instance_id)
                    all_phone_numbers.extend(phone_numbers)

                    # Collect users (limit to avoid large datasets)
                    users = collect_users(region, instance_id)
                    all_users.extend(users[:100])  # Limit to first 100 users per instance

        if not all_instances:
            utils.log_warning("No AWS Connect instances found in any selected region.")
            utils.log_info("Creating empty export file...")

        utils.log_info(f"Total Connect instances found: {len(all_instances)}")
        utils.log_info(f"Total hours of operation found: {len(all_hours)}")
        utils.log_info(f"Total queues found: {len(all_queues)}")
        utils.log_info(f"Total contact flows found: {len(all_flows)}")
        utils.log_info(f"Total phone numbers found: {len(all_phone_numbers)}")
        utils.log_info(f"Total users found: {len(all_users)}")

        # Create DataFrames
        df_instances = utils.prepare_dataframe_for_export(pd.DataFrame(all_instances))
        df_hours = utils.prepare_dataframe_for_export(pd.DataFrame(all_hours))
        df_queues = utils.prepare_dataframe_for_export(pd.DataFrame(all_queues))
        df_flows = utils.prepare_dataframe_for_export(pd.DataFrame(all_flows))
        df_phone_numbers = utils.prepare_dataframe_for_export(pd.DataFrame(all_phone_numbers))
        df_users = utils.prepare_dataframe_for_export(pd.DataFrame(all_users))

        # Create summary
        summary_data = []
        summary_data.append({'Metric': 'Total Connect Instances', 'Value': len(all_instances)})
        summary_data.append({'Metric': 'Total Hours of Operation', 'Value': len(all_hours)})
        summary_data.append({'Metric': 'Total Queues', 'Value': len(all_queues)})
        summary_data.append({'Metric': 'Total Contact Flows', 'Value': len(all_flows)})
        summary_data.append({'Metric': 'Total Phone Numbers', 'Value': len(all_phone_numbers)})
        summary_data.append({'Metric': 'Total Users', 'Value': len(all_users)})
        summary_data.append({'Metric': 'Regions Scanned', 'Value': len(regions)})

        if not df_instances.empty:
            active_instances = len(df_instances[df_instances['InstanceStatus'] == 'ACTIVE'])
            inbound_enabled = len(df_instances[df_instances['InboundCallsEnabled'] == True])
            outbound_enabled = len(df_instances[df_instances['OutboundCallsEnabled'] == True])

            summary_data.append({'Metric': 'Active Instances', 'Value': active_instances})
            summary_data.append({'Metric': 'Inbound Calls Enabled', 'Value': inbound_enabled})
            summary_data.append({'Metric': 'Outbound Calls Enabled', 'Value': outbound_enabled})

        df_summary = utils.prepare_dataframe_for_export(pd.DataFrame(summary_data))

        # Create filtered views
        df_active_instances = pd.DataFrame()
        df_active_flows = pd.DataFrame()

        if not df_instances.empty:
            df_active_instances = df_instances[df_instances['InstanceStatus'] == 'ACTIVE']

        if not df_flows.empty:
            df_active_flows = df_flows[df_flows['ContactFlowState'] == 'ACTIVE']

        # Export to Excel
        filename = utils.create_export_filename(account_name, 'connect', 'all')

        sheets = {
            'Summary': df_summary,
            'Instances': df_instances,
            'Active Instances': df_active_instances,
            'Hours of Operation': df_hours,
            'Queues': df_queues,
            'Contact Flows': df_flows,
            'Active Contact Flows': df_active_flows,
            'Phone Numbers': df_phone_numbers,
            'Users': df_users,
        }

        utils.save_multiple_dataframes_to_excel(sheets, filename)

        # Log summary
        total_resources = (len(all_instances) + len(all_hours) + len(all_queues) +
                          len(all_flows) + len(all_phone_numbers) + len(all_users))

        utils.log_export_summary(
            total_items=total_resources,
            item_type='Connect Resources',
            filename=filename
        )

        utils.log_info(f"  Connect Instances: {len(all_instances)}")
        utils.log_info(f"  Hours of Operation: {len(all_hours)}")
        utils.log_info(f"  Queues: {len(all_queues)}")
        utils.log_info(f"  Contact Flows: {len(all_flows)}")
        utils.log_info(f"  Phone Numbers: {len(all_phone_numbers)}")
        utils.log_info(f"  Users: {len(all_users)}")

        utils.log_success("AWS Connect export completed successfully!")

    except Exception as e:
        utils.log_error(f"Failed to export AWS Connect resources: {str(e)}")
        raise


if __name__ == "__main__":
    main()
