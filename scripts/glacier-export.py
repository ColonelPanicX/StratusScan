#!/usr/bin/env python3
"""
AWS Glacier Export Script

Exports AWS Glacier vault resources (separate from S3 Glacier):
- Glacier Vaults with location and creation date
- Vault configurations and policies
- Vault access policies and lock policies
- Vault notifications (SNS topic configurations)
- Vault inventory metadata

Features:
- Complete Glacier vault inventory
- Vault policy tracking
- Access control analysis
- Notification configuration
- Multi-region support
- Comprehensive multi-worksheet export

Note: Requires glacier:* permissions
Note: Glacier is regional, separate from S3 Glacier storage class
Note: Vault inventories are not real-time (updated every 24 hours)
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import json

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
logger = utils.setup_logging('glacier-export')
utils.log_script_start('glacier-export', 'Export AWS Glacier vaults and configurations')


@utils.aws_error_handler("Collecting Glacier vaults", default_return=[])
def collect_glacier_vaults(region: str) -> List[Dict[str, Any]]:
    """Collect all Glacier vaults in a region."""
    glacier = utils.get_boto3_client('glacier', region_name=region)
    vaults = []

    try:
        paginator = glacier.get_paginator('list_vaults')
        for page in paginator.paginate():
            for vault in page.get('VaultList', []):
                vault_name = vault.get('VaultName', 'N/A')

                # Get vault access policy
                vault_policy = 'N/A'
                try:
                    policy_response = glacier.get_vault_access_policy(vaultName=vault_name)
                    vault_policy = policy_response.get('policy', {}).get('Policy', 'N/A')
                except Exception:
                    pass

                # Get vault lock policy
                lock_policy = 'N/A'
                lock_state = 'N/A'
                try:
                    lock_response = glacier.get_vault_lock(vaultName=vault_name)
                    lock_policy = lock_response.get('Policy', 'N/A')
                    lock_state = lock_response.get('State', 'N/A')
                except Exception:
                    pass

                # Get vault notifications
                notification_config = 'N/A'
                sns_topic = 'N/A'
                try:
                    notif_response = glacier.get_vault_notifications(vaultName=vault_name)
                    notification_config = notif_response.get('vaultNotificationConfig', {})
                    sns_topic = notification_config.get('SNSTopic', 'N/A')
                    events = notification_config.get('Events', [])
                    notification_config = f"Topic: {sns_topic}, Events: {', '.join(events)}" if events else sns_topic
                except Exception:
                    pass

                vaults.append({
                    'Region': region,
                    'VaultName': vault_name,
                    'VaultARN': vault.get('VaultARN', 'N/A'),
                    'CreationDate': vault.get('CreationDate', 'N/A'),
                    'LastInventoryDate': vault.get('LastInventoryDate', 'N/A'),
                    'NumberOfArchives': vault.get('NumberOfArchives', 0),
                    'SizeInBytes': vault.get('SizeInBytes', 0),
                    'SizeInGB': round(vault.get('SizeInBytes', 0) / (1024**3), 2) if vault.get('SizeInBytes') else 0,
                    'HasAccessPolicy': 'Yes' if vault_policy != 'N/A' else 'No',
                    'VaultAccessPolicy': vault_policy if len(str(vault_policy)) < 500 else f"{str(vault_policy)[:500]}...",
                    'HasLockPolicy': 'Yes' if lock_policy != 'N/A' else 'No',
                    'LockPolicyState': lock_state,
                    'VaultLockPolicy': lock_policy if len(str(lock_policy)) < 500 else f"{str(lock_policy)[:500]}...",
                    'NotificationConfig': notification_config,
                    'SNSTopic': sns_topic,
                })
    except Exception:
        pass

    return vaults


@utils.aws_error_handler("Collecting vault tags", default_return=[])
def collect_vault_tags(region: str, vault_arns: List[str]) -> List[Dict[str, Any]]:
    """Collect tags for Glacier vaults."""
    glacier = utils.get_boto3_client('glacier', region_name=region)
    vault_tags = []

    for vault_arn in vault_arns:
        try:
            # Extract vault name from ARN
            vault_name = vault_arn.split('/')[-1]

            response = glacier.list_tags_for_vault(vaultName=vault_name)
            tags = response.get('Tags', {})

            if tags:
                # Format tags
                tag_list = [f"{k}={v}" for k, v in tags.items()]

                vault_tags.append({
                    'Region': region,
                    'VaultName': vault_name,
                    'VaultARN': vault_arn,
                    'Tags': ', '.join(tag_list),
                })
            else:
                vault_tags.append({
                    'Region': region,
                    'VaultName': vault_name,
                    'VaultARN': vault_arn,
                    'Tags': 'No tags',
                })
        except Exception:
            pass

    return vault_tags


def main():
    """Main execution function."""
    try:
        # Get account information
        account_id, account_name = utils.get_account_info()
        utils.log_info(f"Exporting Glacier vaults for account: {account_name} ({account_id})")

        # Prompt for regions
        utils.log_info("Glacier is a regional service (separate from S3 Glacier storage class).")
        regions = utils.prompt_region_selection(
            service_name="Glacier",
            default_to_all=False
        )

        if not regions:
            utils.log_error("No regions selected. Exiting.")
            return

        utils.log_info(f"Scanning {len(regions)} region(s) for Glacier vaults...")

        # Collect all resources
        all_vaults = []
        all_vault_tags = []

        for idx, region in enumerate(regions, 1):
            utils.log_info(f"[{idx}/{len(regions)}] Processing region: {region}")

            # Collect vaults
            vaults = collect_glacier_vaults(region)
            if vaults:
                utils.log_info(f"  Found {len(vaults)} Glacier vault(s)")
                all_vaults.extend(vaults)

                # Collect vault tags
                vault_arns = [v['VaultARN'] for v in vaults if v['VaultARN'] != 'N/A']
                if vault_arns:
                    vault_tags = collect_vault_tags(region, vault_arns)
                    all_vault_tags.extend(vault_tags)

        if not all_vaults:
            utils.log_warning("No Glacier vaults found in any selected region.")
            utils.log_info("Creating empty export file...")

        utils.log_info(f"Total Glacier vaults found: {len(all_vaults)}")
        utils.log_info(f"Total vault tags found: {len(all_vault_tags)}")

        # Create DataFrames
        df_vaults = utils.prepare_dataframe_for_export(pd.DataFrame(all_vaults))
        df_vault_tags = utils.prepare_dataframe_for_export(pd.DataFrame(all_vault_tags))

        # Create summary
        summary_data = []
        summary_data.append({'Metric': 'Total Glacier Vaults', 'Value': len(all_vaults)})
        summary_data.append({'Metric': 'Regions Scanned', 'Value': len(regions)})

        if not df_vaults.empty:
            total_archives = df_vaults['NumberOfArchives'].sum()
            total_size_gb = df_vaults['SizeInGB'].sum()
            vaults_with_policies = len(df_vaults[df_vaults['HasAccessPolicy'] == 'Yes'])
            vaults_with_locks = len(df_vaults[df_vaults['HasLockPolicy'] == 'Yes'])
            vaults_with_notifications = len(df_vaults[df_vaults['SNSTopic'] != 'N/A'])

            summary_data.append({'Metric': 'Total Archives', 'Value': int(total_archives)})
            summary_data.append({'Metric': 'Total Size (GB)', 'Value': round(total_size_gb, 2)})
            summary_data.append({'Metric': 'Vaults with Access Policies', 'Value': vaults_with_policies})
            summary_data.append({'Metric': 'Vaults with Lock Policies', 'Value': vaults_with_locks})
            summary_data.append({'Metric': 'Vaults with Notifications', 'Value': vaults_with_notifications})

        df_summary = utils.prepare_dataframe_for_export(pd.DataFrame(summary_data))

        # Create filtered views
        df_with_policies = pd.DataFrame()
        df_with_locks = pd.DataFrame()
        df_with_notifications = pd.DataFrame()

        if not df_vaults.empty:
            df_with_policies = df_vaults[df_vaults['HasAccessPolicy'] == 'Yes']
            df_with_locks = df_vaults[df_vaults['HasLockPolicy'] == 'Yes']
            df_with_notifications = df_vaults[df_vaults['SNSTopic'] != 'N/A']

        # Export to Excel
        filename = utils.create_export_filename(account_name, 'glacier', 'all')

        sheets = {
            'Summary': df_summary,
            'All Vaults': df_vaults,
            'Vaults with Policies': df_with_policies,
            'Vaults with Locks': df_with_locks,
            'Vaults with Notifications': df_with_notifications,
            'Vault Tags': df_vault_tags,
        }

        utils.save_multiple_dataframes_to_excel(sheets, filename)

        # Log summary
        utils.log_export_summary(
            total_items=len(all_vaults),
            item_type='Glacier Vaults',
            filename=filename
        )

        utils.log_info(f"  Glacier Vaults: {len(all_vaults)}")
        if not df_vaults.empty:
            utils.log_info(f"  Total Archives: {int(df_vaults['NumberOfArchives'].sum())}")
            utils.log_info(f"  Total Size: {round(df_vaults['SizeInGB'].sum(), 2)} GB")

        utils.log_success("Glacier export completed successfully!")

    except Exception as e:
        utils.log_error(f"Failed to export Glacier vaults: {str(e)}")
        raise


if __name__ == "__main__":
    main()
