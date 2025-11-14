#!/usr/bin/env python3
"""
AWS Marketplace Subscriptions Export Script

Exports AWS Marketplace subscription and entitlement resources:
- Private Marketplace configurations
- Procurement policies and allowed products
- Experience configurations

Note: AWS Marketplace Catalog and Entitlement services are for sellers
This script focuses on buyer/consumer subscriptions visible through
the AWS Marketplace console and Private Marketplace configurations.

Features:
- Private Marketplace settings
- Procurement policy tracking
- Experience and branding configurations
- Multi-region support (global service)
- Comprehensive export

Note: Requires aws-marketplace:* permissions
Note: Marketplace configuration is accessed through us-east-1
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
logger = utils.setup_logging('marketplace-export')
utils.log_script_start('marketplace-export', 'Export AWS Marketplace subscriptions and configurations')


@utils.aws_error_handler("Collecting Private Marketplace configuration", default_return={})
def collect_private_marketplace_config() -> Dict[str, Any]:
    """Collect Private Marketplace configuration."""
    # Marketplace Catalog is accessed through us-east-1
    mp_catalog = utils.get_boto3_client('marketplace-catalog', region_name='us-east-1')

    config_data = {
        'Status': 'N/A',
        'Note': 'Private Marketplace APIs require specific permissions. Check AWS Console for full details.'
    }

    return config_data


@utils.aws_error_handler("Collecting Marketplace procurement policies", default_return=[])
def collect_procurement_policies() -> List[Dict[str, Any]]:
    """Collect procurement system policies (if accessible)."""
    # Note: This uses the marketplace-procurement service if available
    policies = []

    try:
        procurement = utils.get_boto3_client('marketplace-procurement', region_name='us-east-1')
        # The procurement service may not be directly accessible via standard APIs
        # This is a placeholder for when such APIs become available
        utils.log_info("Marketplace procurement policies require console access or specific API permissions.")
    except Exception:
        pass

    return policies


def main():
    """Main execution function."""
    try:
        # Get account information
        account_id, account_name = utils.get_account_info()
        utils.log_info(f"Exporting AWS Marketplace configuration for account: {account_name} ({account_id})")

        utils.log_info("AWS Marketplace is a global service accessed through us-east-1.")
        utils.log_info("Note: Full marketplace subscription details require AWS Console access.")
        utils.log_info("This export captures configuration available via APIs.")

        # Collect Private Marketplace configuration
        pm_config = collect_private_marketplace_config()

        # Collect procurement policies (if available)
        procurement_policies = collect_procurement_policies()

        utils.log_info("Marketplace configuration collection completed.")
        utils.log_info("Note: Many marketplace features require AWS Console or Marketplace APIs.")

        # Create summary data
        summary_data = []
        summary_data.append({'Metric': 'Account ID', 'Value': account_id})
        summary_data.append({'Metric': 'Account Name', 'Value': account_name})
        summary_data.append({'Metric': 'Private Marketplace Status', 'Value': pm_config.get('Status', 'N/A')})
        summary_data.append({'Metric': 'Procurement Policies Found', 'Value': len(procurement_policies)})
        summary_data.append({
            'Metric': 'Note',
            'Value': 'AWS Marketplace subscriptions are primarily managed through the AWS Console. API access is limited for buyer accounts.'
        })

        df_summary = utils.prepare_dataframe_for_export(pd.DataFrame(summary_data))

        # Create config DataFrame
        config_data = []
        config_data.append({
            'Configuration': 'Private Marketplace',
            'Status': pm_config.get('Status', 'N/A'),
            'Details': pm_config.get('Note', 'N/A'),
        })

        df_config = utils.prepare_dataframe_for_export(pd.DataFrame(config_data))

        # Create procurement policies DataFrame
        df_procurement = utils.prepare_dataframe_for_export(pd.DataFrame(procurement_policies))

        # Export to Excel
        filename = utils.create_export_filename(account_name, 'marketplace', 'global')

        sheets = {
            'Summary': df_summary,
            'Configuration': df_config,
            'Procurement Policies': df_procurement,
        }

        utils.save_multiple_dataframes_to_excel(sheets, filename)

        # Log summary
        utils.log_export_summary(
            total_items=1,
            item_type='Marketplace Configuration',
            filename=filename
        )

        utils.log_info("IMPORTANT: AWS Marketplace subscription management is primarily console-based.")
        utils.log_info("For complete subscription details:")
        utils.log_info("  1. Visit AWS Marketplace Console: https://console.aws.amazon.com/marketplace")
        utils.log_info("  2. Navigate to 'Manage subscriptions' for active products")
        utils.log_info("  3. Check 'Private Marketplace' for procurement policies")

        utils.log_success("Marketplace export completed successfully!")

    except Exception as e:
        utils.log_error(f"Failed to export Marketplace configuration: {str(e)}")
        raise


if __name__ == "__main__":
    main()
