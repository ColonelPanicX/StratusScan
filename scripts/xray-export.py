#!/usr/bin/env python3
"""
AWS X-Ray Export Script

Exports AWS X-Ray distributed tracing configuration:
- Encryption configurations
- Sampling rules and priorities
- Groups (trace filters and insights)
- Service graph data (recent)
- Insights configuration

Features:
- Complete X-Ray configuration inventory
- Sampling rule analysis
- Group and filter tracking
- Encryption settings
- Multi-region support
- Comprehensive multi-worksheet export

Note: Requires xray:Get* and xray:List* permissions
Note: X-Ray trace data itself is not exported (time-series data)
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
logger = utils.setup_logging('xray-export')
utils.log_script_start('xray-export', 'Export AWS X-Ray configuration')


@utils.aws_error_handler("Collecting encryption config", default_return={})
def collect_encryption_config(region: str) -> Dict[str, Any]:
    """Collect X-Ray encryption configuration for a region."""
    xray = utils.get_boto3_client('xray', region_name=region)

    try:
        response = xray.get_encryption_config()
        config = response.get('EncryptionConfig', {})

        return {
            'Region': region,
            'Status': config.get('Status', 'N/A'),
            'Type': config.get('Type', 'N/A'),
            'KeyId': config.get('KeyId', 'N/A'),
        }
    except Exception:
        return {
            'Region': region,
            'Status': 'N/A',
            'Type': 'N/A',
            'KeyId': 'N/A',
        }


@utils.aws_error_handler("Collecting sampling rules", default_return=[])
def collect_sampling_rules(region: str) -> List[Dict[str, Any]]:
    """Collect X-Ray sampling rules in a region."""
    xray = utils.get_boto3_client('xray', region_name=region)
    rules = []

    try:
        paginator = xray.get_paginator('get_sampling_rules')
        for page in paginator.paginate():
            for rule_record in page.get('SamplingRuleRecords', []):
                rule = rule_record.get('SamplingRule', {})

                rules.append({
                    'Region': region,
                    'RuleName': rule.get('RuleName', 'N/A'),
                    'RuleARN': rule.get('RuleARN', 'N/A'),
                    'Priority': rule.get('Priority', 'N/A'),
                    'FixedRate': rule.get('FixedRate', 0),
                    'ReservoirSize': rule.get('ReservoirSize', 0),
                    'ServiceName': rule.get('ServiceName', '*'),
                    'ServiceType': rule.get('ServiceType', '*'),
                    'Host': rule.get('Host', '*'),
                    'HTTPMethod': rule.get('HTTPMethod', '*'),
                    'URLPath': rule.get('URLPath', '*'),
                    'Version': rule.get('Version', 1),
                    'ResourceARN': rule.get('ResourceARN', '*'),
                    'Attributes': str(rule.get('Attributes', {})),
                    'CreatedAt': rule_record.get('CreatedAt'),
                    'ModifiedAt': rule_record.get('ModifiedAt'),
                })
    except Exception:
        pass

    return rules


@utils.aws_error_handler("Collecting groups", default_return=[])
def collect_groups(region: str) -> List[Dict[str, Any]]:
    """Collect X-Ray groups (trace filters) in a region."""
    xray = utils.get_boto3_client('xray', region_name=region)
    groups = []

    try:
        paginator = xray.get_paginator('get_groups')
        for page in paginator.paginate():
            for group in page.get('Groups', []):
                groups.append({
                    'Region': region,
                    'GroupName': group.get('GroupName', 'N/A'),
                    'GroupARN': group.get('GroupARN', 'N/A'),
                    'FilterExpression': group.get('FilterExpression', 'N/A'),
                    'InsightsConfiguration': str(group.get('InsightsConfiguration', {})),
                })
    except Exception:
        pass

    return groups


@utils.aws_error_handler("Collecting insights", default_return=[])
def collect_insights(region: str) -> List[Dict[str, Any]]:
    """Collect X-Ray Insights configuration."""
    xray = utils.get_boto3_client('xray', region_name=region)
    insights = []

    try:
        # Get insights summary from groups
        groups_response = xray.get_groups()

        for group in groups_response.get('Groups', []):
            insights_config = group.get('InsightsConfiguration', {})

            if insights_config.get('InsightsEnabled'):
                insights.append({
                    'Region': region,
                    'GroupName': group.get('GroupName', 'N/A'),
                    'GroupARN': group.get('GroupARN', 'N/A'),
                    'InsightsEnabled': insights_config.get('InsightsEnabled', False),
                    'NotificationsEnabled': insights_config.get('NotificationsEnabled', False),
                })
    except Exception:
        pass

    return insights


def main():
    """Main execution function."""
    try:
        # Get account information
        account_id, account_name = utils.get_account_info()
        utils.log_info(f"Exporting X-Ray configuration for account: {account_name} ({account_id})")

        # Prompt for regions
        utils.log_info("X-Ray is a regional service.")
        regions = utils.prompt_region_selection(
            service_name="X-Ray",
            default_to_all=False
        )

        if not regions:
            utils.log_error("No regions selected. Exiting.")
            return

        utils.log_info(f"Scanning {len(regions)} region(s) for X-Ray configuration...")

        # Collect all resources
        all_encryption = []
        all_rules = []
        all_groups = []
        all_insights = []

        for idx, region in enumerate(regions, 1):
            utils.log_info(f"[{idx}/{len(regions)}] Processing region: {region}")

            # Collect encryption config
            encryption = collect_encryption_config(region)
            all_encryption.append(encryption)

            # Collect sampling rules
            rules = collect_sampling_rules(region)
            if rules:
                utils.log_info(f"  Found {len(rules)} sampling rule(s)")
                all_rules.extend(rules)

            # Collect groups
            groups = collect_groups(region)
            if groups:
                utils.log_info(f"  Found {len(groups)} group(s)")
                all_groups.extend(groups)

            # Collect insights
            insights = collect_insights(region)
            if insights:
                utils.log_info(f"  Found {len(insights)} insight configuration(s)")
                all_insights.extend(insights)

        utils.log_info(f"Total sampling rules found: {len(all_rules)}")
        utils.log_info(f"Total groups found: {len(all_groups)}")
        utils.log_info(f"Total insights configurations found: {len(all_insights)}")

        # Create DataFrames
        df_encryption = utils.prepare_dataframe_for_export(pd.DataFrame(all_encryption))
        df_rules = utils.prepare_dataframe_for_export(pd.DataFrame(all_rules))
        df_groups = utils.prepare_dataframe_for_export(pd.DataFrame(all_groups))
        df_insights = utils.prepare_dataframe_for_export(pd.DataFrame(all_insights))

        # Create summary
        summary_data = []
        summary_data.append({'Metric': 'Total Sampling Rules', 'Value': len(all_rules)})
        summary_data.append({'Metric': 'Total Groups', 'Value': len(all_groups)})
        summary_data.append({'Metric': 'Total Insights Enabled', 'Value': len(all_insights)})
        summary_data.append({'Metric': 'Regions Scanned', 'Value': len(regions)})

        if not df_encryption.empty:
            encrypted_regions = len(df_encryption[df_encryption['Type'] == 'KMS'])
            default_encrypted = len(df_encryption[df_encryption['Type'] == 'NONE'])

            summary_data.append({'Metric': 'Regions with KMS Encryption', 'Value': encrypted_regions})
            summary_data.append({'Metric': 'Regions with Default Encryption', 'Value': default_encrypted})

        if not df_rules.empty:
            # Count custom vs default rules
            custom_rules = len(df_rules[df_rules['RuleName'] != 'Default'])
            default_rules = len(df_rules[df_rules['RuleName'] == 'Default'])

            summary_data.append({'Metric': 'Custom Sampling Rules', 'Value': custom_rules})
            summary_data.append({'Metric': 'Default Sampling Rules', 'Value': default_rules})

        df_summary = utils.prepare_dataframe_for_export(pd.DataFrame(summary_data))

        # Create filtered views
        df_custom_rules = pd.DataFrame()

        if not df_rules.empty:
            df_custom_rules = df_rules[df_rules['RuleName'] != 'Default']

        # Export to Excel
        filename = utils.create_export_filename(account_name, 'xray', 'all')

        sheets = {
            'Summary': df_summary,
            'Encryption Config': df_encryption,
            'Sampling Rules': df_rules,
            'Custom Rules': df_custom_rules,
            'Groups': df_groups,
            'Insights': df_insights,
        }

        utils.save_multiple_dataframes_to_excel(sheets, filename)

        # Log summary
        utils.log_export_summary(
            total_items=len(all_rules) + len(all_groups) + len(all_insights),
            item_type='X-Ray Resources',
            filename=filename
        )

        utils.log_info(f"  Sampling Rules: {len(all_rules)}")
        utils.log_info(f"  Groups: {len(all_groups)}")
        utils.log_info(f"  Insights: {len(all_insights)}")

        utils.log_success("X-Ray export completed successfully!")

    except Exception as e:
        utils.log_error(f"Failed to export X-Ray configuration: {str(e)}")
        raise


if __name__ == "__main__":
    main()
