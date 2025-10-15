#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS EBS Snapshots Export Tool
Version: v2.0.0
Date: AUG-19-2025

Description:
This script exports Amazon EBS snapshot information across AWS regions or a specific
AWS region into an Excel spreadsheet. The export includes snapshot name, ID,
description, size information, encryption status, storage tier, and creation date.
"""

import sys
import os
import boto3
import datetime
import time
from botocore.exceptions import ClientError
from pathlib import Path

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

def print_title():
    """
    Print the title banner and get account information.
    
    Returns:
        tuple: (account_id, account_name)
    """
    print("====================================================================")
    print("                   AWS RESOURCE SCANNER                             ")
    print("====================================================================")
    print("AWS EBS SNAPSHOTS EXPORT TOOL")
    print("====================================================================")
    print("Version: v2.0.0                                Date: AUG-19-2025")
    print("Environment: AWS Commercial")
    print("====================================================================")
    
    # Get the current AWS account ID
    try:
        # Create a new STS client to get the current account ID
        sts_client = boto3.client('sts')
        # Get account ID from caller identity
        account_id = sts_client.get_caller_identity()['Account']
        
        # Map the account ID to an account name using utils module
        account_name = utils.get_account_name(account_id, default=account_id)
        
        print(f"Account ID: {account_id}")
        print(f"Account Name: {account_name}")
    except Exception as e:
        print(f"Could not determine account information: {e}")
        account_id = "UNKNOWN"
        account_name = "UNKNOWN-ACCOUNT"
    
    print("====================================================================")
    return account_id, account_name

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
        print(f"\nPackages required but not installed: {', '.join(missing_packages)}")
        response = input("Would you like to install these packages now? (y/n): ").lower()
        
        if response == 'y':
            import subprocess
            for package in missing_packages:
                print(f"Installing {package}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    utils.log_success(f"Successfully installed {package}")
                except Exception as e:
                    utils.log_error(f"Error installing {package}", e)
                    print("Please install it manually with: pip install " + package)
                    return False
            return True
        else:
            print("Cannot proceed without required dependencies.")
            return False
    
    return True

def get_aws_regions():
    """
    Get a list of available AWS regions.

    Returns:
        list: List of AWS region names
    """
    try:
        # Use utils function to get accessible AWS regions
        regions = utils.get_available_aws_regions()
        if not regions:
            utils.log_warning("No accessible AWS regions found. Using default list.")
            regions = utils.get_aws_regions()
        return regions
    except Exception as e:
        utils.log_error("Error getting AWS regions", e)
        # Return default AWS regions if API call fails
        return utils.get_aws_regions()

def is_valid_aws_region(region_name):
    """
    Check if a region name is a valid AWS region.

    Args:
        region_name (str): The region name to validate

    Returns:
        bool: True if valid, False otherwise
    """
    return utils.validate_aws_region(region_name)

def get_snapshot_name(snapshot):
    """
    Extract the snapshot name from tags.
    
    Args:
        snapshot (dict): The snapshot object from the API response
        
    Returns:
        str: The name of the snapshot or 'N/A' if not present
    """
    if 'Tags' in snapshot:
        for tag in snapshot['Tags']:
            if tag['Key'] == 'Name':
                return tag['Value']
    return 'N/A'

def format_tags(tags):
    """
    Format snapshot tags in the format "Key1:Value1, Key2:Value2, etc..."
    
    Args:
        tags (list): List of tag dictionaries with Key and Value
        
    Returns:
        str: Formatted tags string or 'N/A' if no tags
    """
    if not tags:
        return 'N/A'
    
    formatted_tags = []
    for tag in tags:
        if 'Key' in tag and 'Value' in tag:
            formatted_tags.append(f"{tag['Key']}:{tag['Value']}")
    
    if formatted_tags:
        return ', '.join(formatted_tags)
    else:
        return 'N/A'

def get_snapshots(region):
    """
    Get all EBS snapshots owned by the account in a specific AWS region.

    Args:
        region (str): AWS region name

    Returns:
        list: List of dictionaries with snapshot information
    """
    # Validate region is AWS
    if not utils.validate_aws_region(region):
        utils.log_error(f"Invalid AWS region: {region}")
        return []
    
    snapshots_data = []
    
    try:
        # Create an EC2 client for the specified AWS region
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Use pagination to handle large number of snapshots
        paginator = ec2_client.get_paginator('describe_snapshots')
        page_iterator = paginator.paginate(OwnerIds=['self'])
        
        for page in page_iterator:
            for snapshot in page['Snapshots']:
                # Get snapshot name from tags
                snapshot_name = get_snapshot_name(snapshot)
                
                # Extract standard snapshot attributes
                snapshot_id = snapshot['SnapshotId']
                volume_id = snapshot.get('VolumeId', 'N/A')
                description = snapshot.get('Description', 'N/A')
                volume_size = snapshot.get('VolumeSize', 0)  # Size in GB
                
                # Handle start time (convert to string without timezone)
                start_time = snapshot.get('StartTime', '')
                start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else 'N/A'
                
                # Get encryption status
                encryption = 'Yes' if snapshot.get('Encrypted', False) else 'No'
                
                # Get storage tier (Standard or Archive)
                storage_tier = snapshot.get('StorageTier', 'Standard')
                
                # Get state and progress
                state = snapshot.get('State', 'N/A')
                progress = snapshot.get('Progress', 'N/A')
                
                # Get owner ID with account name mapping
                owner_id = snapshot.get('OwnerId', 'N/A')
                owner_formatted = utils.get_account_name_formatted(owner_id)
                
                # Get KMS key ID if encrypted
                kms_key_id = snapshot.get('KmsKeyId', 'N/A') if snapshot.get('Encrypted', False) else 'N/A'
                
                # Format tags
                snapshot_tags = format_tags(snapshot.get('Tags', []))
                
                # Additional data processing for specific attributes
                # Full snapshot size is not directly available via standard API
                full_snapshot_size_gb = 'N/A'
                
                # Add to results
                snapshots_data.append({
                    'Name': snapshot_name,
                    'Snapshot ID': snapshot_id,
                    'Volume ID': volume_id,
                    'Description': description,
                    'Volume Size (GB)': volume_size,
                    'Full Snapshot Size': full_snapshot_size_gb,
                    'Storage Tier': storage_tier,
                    'State': state,
                    'Progress': progress,
                    'Started': start_time_str,
                    'Encryption': encryption,
                    'KMS Key ID': kms_key_id,
                    'Owner ID': owner_formatted,
                    'Region': region,
                    'Tags': snapshot_tags
                })
                
    except Exception as e:
        utils.log_error(f"Error getting snapshots in AWS region {region}", e)
    
    return snapshots_data

def main():
    """
    Main function to execute the script.
    """
    try:
        # Print title and get account information
        account_id, account_name = print_title()
        
        # Check dependencies
        if not check_dependencies():
            sys.exit(1)
        
        # Now import pandas (after dependency check)
        import pandas as pd
        
        if account_name == "UNKNOWN-ACCOUNT":
            proceed = input("Unable to determine account name. Proceed anyway? (y/n): ").lower()
            if proceed != 'y':
                print("Exiting script...")
                sys.exit(0)
        
        # Get AWS region preference from user
        print("\nAWS Region Selection:")
        print("Would you like the information for all AWS regions or a specific region?")
        print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1")
        region_choice = input("If all, write \"all\", or specify an AWS region name: ").strip().lower()
        
        if region_choice != "all":
            if not is_valid_aws_region(region_choice):
                utils.log_warning(f"'{region_choice}' is not a valid AWS region.")
                utils.log_info("Valid AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1")
                utils.log_info("Checking all AWS regions instead.")
                region_choice = "all"
        
        # Determine AWS regions to process
        if region_choice == "all":
            utils.log_info("Retrieving available AWS regions...")
            regions = get_aws_regions()
            if not regions:
                utils.log_error("No AWS regions found. Please check your AWS credentials and permissions.")
                sys.exit(1)
            utils.log_info(f"Found {len(regions)} AWS regions to scan: {', '.join(regions)}")
        else:
            regions = [region_choice]
            utils.log_info(f"Scanning only the {region_choice} AWS region.")
        
        # Collect snapshot data from all specified AWS regions
        all_snapshots = []
        total_regions = len(regions)

        for i, region in enumerate(regions, 1):
            progress = (i / total_regions) * 100
            utils.log_info(f"[{progress:.1f}%] Processing AWS region: {region} ({i}/{total_regions})")
            
            region_snapshots = get_snapshots(region)
            all_snapshots.extend(region_snapshots)
            
            utils.log_info(f"Found {len(region_snapshots)} snapshots in {region}")
            
            # Add a small delay to avoid API throttling
            time.sleep(0.5)
        
        # Print summary
        total_snapshots = len(all_snapshots)
        utils.log_success(f"Total EBS snapshots found across all AWS regions: {total_snapshots}")
        
        if total_snapshots == 0:
            utils.log_warning("No snapshots found. Nothing to export.")
            sys.exit(0)
        
        # Create DataFrame from snapshot data
        utils.log_info("Preparing data for export to Excel format...")
        df = pd.DataFrame(all_snapshots)
        
        # Generate filename with region info
        region_suffix = "" if region_choice == "all" else f"-{region_choice}"

        # Use utils module to generate filename
        filename = utils.create_export_filename(
            account_name,
            "ebs-snapshots",
            region_suffix if region_suffix else None,
            datetime.datetime.now().strftime("%m.%d.%Y")
        )
        
        # Save the data using the utility function
        output_path = utils.save_dataframe_to_excel(df, filename)
        
        if output_path:
            utils.log_success("AWS EBS snapshots data exported successfully!")
            utils.log_info(f"File location: {output_path}")
            utils.log_info(f"Export contains data from {len(regions)} AWS region(s)")
            utils.log_info(f"Total snapshots exported: {total_snapshots}")
            print("\nScript execution completed.")
        else:
            utils.log_error("Error exporting data. Please check the logs.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        utils.log_error("Unexpected error occurred", e)
        sys.exit(1)

if __name__ == "__main__":
    main()