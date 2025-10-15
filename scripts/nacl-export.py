#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Network ACL (NACL) Data Export
Version: v2.0.0
Date: AUG-26-2025

Description:
This script exports Network ACL (NACL) information from AWS regions, including NACL ID,
VPC ID, inbound/outbound rules, subnet associations, and tags. The data is exported to an Excel
file for analysis and compliance purposes.
"""

import sys
import os
import boto3
import datetime
import time
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
        response = input("Would you like to install these packages now? (y/n): ").lower()
        
        if response == 'y':
            import subprocess
            for package in missing_packages:
                utils.log_info(f"Installing {package}...")
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

def print_title():
    """
    Print the script title banner and get account info.
    
    Returns:
        tuple: (account_id, account_name)
    """
    print("====================================================================")
    print("                   AWS RESOURCE SCANNER                            ")
    print("====================================================================")
    print("AWS NETWORK ACL (NACL) DATA EXPORT TOOL")
    print("====================================================================")
    print("Version: v2.0.0                                Date: AUG-26-2025")
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
        utils.log_error("Could not determine account information", e)
        account_id = "UNKNOWN"
        account_name = "UNKNOWN-ACCOUNT"
    
    print("====================================================================")
    return account_id, account_name

def get_aws_regions():
    """
    Get a list of available AWS regions.

    Returns:
        list: List of AWS region names
    """
    try:
        # Use utils function to get available AWS regions
        regions = utils.get_available_aws_regions()
        if not regions:
            utils.log_warning("No accessible AWS regions found. Using default list.")
            regions = utils.get_aws_regions()
        return regions
    except Exception as e:
        utils.log_error("Error getting AWS regions", e)
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

def get_tag_value(tags, key='Name'):
    """
    Get a tag value from a list of tags.
    
    Args:
        tags: List of tag dictionaries
        key: The tag key to look for
        
    Returns:
        str: The tag value or "N/A" if not found
    """
    if not tags:
        return "N/A"
    
    for tag in tags:
        if tag['Key'] == key:
            return tag['Value']
    
    return "N/A"

def format_rule(rule):
    """
    Format a NACL rule into a readable string.
    
    Args:
        rule: The NACL rule dictionary
        
    Returns:
        str: A formatted string representation of the rule
    """
    rule_number = rule.get('RuleNumber', 'N/A')
    protocol = rule.get('Protocol', 'N/A')
    
    # Convert protocol number to name if possible
    if protocol == '-1':
        protocol = 'All'
    elif protocol == '6':
        protocol = 'TCP'
    elif protocol == '17':
        protocol = 'UDP'
    elif protocol == '1':
        protocol = 'ICMP'
    
    # Get port range
    port_range = f"{rule.get('PortRange', {}).get('From', 'All')}-{rule.get('PortRange', {}).get('To', 'All')}"
    if port_range == "All-All":
        port_range = "All"
    
    cidr = rule.get('CidrBlock', rule.get('Ipv6CidrBlock', 'N/A'))
    action = rule.get('RuleAction', 'N/A')
    
    return f"{rule_number}: {action.upper()} {protocol}:{port_range} from {cidr}"

def get_nacl_data(region):
    """
    Get Network ACL information for a specific AWS region.

    Args:
        region: AWS region name

    Returns:
        list: List of dictionaries with NACL information
    """
    # Validate region is AWS
    if not utils.validate_aws_region(region):
        utils.log_error(f"Invalid AWS region: {region}")
        return []
    
    nacl_data = []
    
    try:
        # Create EC2 client for the specified AWS region
        ec2_client = boto3.client('ec2', region_name=region)
        
        # Get all NACLs in the region
        response = ec2_client.describe_network_acls()
        
        for nacl in response.get('NetworkAcls', []):
            nacl_id = nacl.get('NetworkAclId', 'N/A')
            vpc_id = nacl.get('VpcId', 'N/A')
            is_default = nacl.get('IsDefault', False)
            
            # Get NACL name from tags
            nacl_name = get_tag_value(nacl.get('Tags', []))
            
            # Format tags as a string
            tags_str = '; '.join([f"{tag['Key']}={tag['Value']}" for tag in nacl.get('Tags', [])])
            if not tags_str:
                tags_str = "N/A"
            
            # Get inbound and outbound rules
            inbound_rules = [rule for rule in nacl.get('Entries', []) if not rule.get('Egress', False)]
            outbound_rules = [rule for rule in nacl.get('Entries', []) if rule.get('Egress', False)]
            
            # Format rules as strings
            inbound_rules_str = '; '.join([format_rule(rule) for rule in sorted(inbound_rules, key=lambda x: x.get('RuleNumber', 0))])
            outbound_rules_str = '; '.join([format_rule(rule) for rule in sorted(outbound_rules, key=lambda x: x.get('RuleNumber', 0))])
            
            if not inbound_rules_str:
                inbound_rules_str = "N/A"
            if not outbound_rules_str:
                outbound_rules_str = "N/A"
            
            # Get subnet associations
            subnet_associations = []
            for assoc in nacl.get('Associations', []):
                subnet_id = assoc.get('SubnetId', 'N/A')
                if subnet_id != 'N/A':
                    subnet_associations.append(subnet_id)
            
            subnet_associations_str = '; '.join(subnet_associations) if subnet_associations else "N/A"
            
            # Get owner information
            owner_id = nacl.get('OwnerId', 'N/A')
            owner_formatted = utils.get_account_name_formatted(owner_id)
            
            # Add NACL data
            nacl_entry = {
                'Region': region,
                'NACL ID': nacl_id,
                'NACL Name': nacl_name,
                'VPC ID': vpc_id,
                'Is Default': 'Yes' if is_default else 'No',
                'Inbound Rules': inbound_rules_str,
                'Outbound Rules': outbound_rules_str,
                'Subnet Associations': subnet_associations_str,
                'Owner ID': owner_formatted,
                'Tags': tags_str
            }
            
            nacl_data.append(nacl_entry)
            
    except Exception as e:
        utils.log_error(f"Error collecting NACL data in AWS region {region}", e)
    
    return nacl_data

def main():
    """
    Main function to execute the script.
    """
    try:
        # Print title and get account information
        account_id, account_name = print_title()
        
        # Check for required dependencies
        if not check_dependencies():
            sys.exit(1)
            
        # Now import pandas after ensuring it's installed
        import pandas as pd
        
        if account_name == "UNKNOWN-ACCOUNT":
            proceed = utils.prompt_for_confirmation("Unable to determine account name. Proceed anyway?", default=False)
            if not proceed:
                utils.log_info("Exiting script...")
                sys.exit(0)
        
        # Ask for AWS region selection
        print("\nAWS Region Selection:")
        print("Would you like the information for all AWS regions or a specific region?")
        print("Available AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1")
        region_choice = input("If all, write \"all\", or specify an AWS region name: ").strip().lower()
        
        # Determine regions to scan
        if region_choice == "all":
            utils.log_info("Retrieving all available AWS regions...")
            regions = get_aws_regions()
            if not regions:
                utils.log_error("No AWS regions found. Please check your AWS credentials and permissions.")
                sys.exit(1)
            utils.log_info(f"Found {len(regions)} AWS regions to scan: {', '.join(regions)}")
            region_suffix = ""
        else:
            # Validate the provided region is an AWS region
            if is_valid_aws_region(region_choice):
                regions = [region_choice]
                utils.log_info(f"Scanning only the {region_choice} AWS region.")
                region_suffix = region_choice
            else:
                utils.log_warning(f"'{region_choice}' is not a valid AWS region.")
                utils.log_info("Valid AWS regions: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1")
                utils.log_info("Defaulting to all AWS regions...")
                regions = get_aws_regions()
                utils.log_info(f"Found {len(regions)} AWS regions to scan: {', '.join(regions)}")
                region_suffix = ""
        
        # Collect NACL data from all specified AWS regions
        all_nacl_data = []

        utils.log_info("Collecting Network ACL data from AWS regions...")
        for i, region in enumerate(regions, 1):
            progress = (i / len(regions)) * 100
            utils.log_info(f"[{progress:.1f}%] Processing AWS region {i}/{len(regions)}: {region}")
            region_data = get_nacl_data(region)
            all_nacl_data.extend(region_data)
            utils.log_info(f"Found {len(region_data)} NACLs in {region}")
            
            # Add a small delay to avoid API throttling
            time.sleep(0.5)
        
        # Check if we found any NACLs
        if not all_nacl_data:
            utils.log_warning("No Network ACLs found in any AWS region. Exiting...")
            sys.exit(0)
        
        # Create DataFrame
        utils.log_info("Preparing data for export to Excel format...")
        df = pd.DataFrame(all_nacl_data)
        
        # Generate filename
        current_date = datetime.datetime.now().strftime("%m.%d.%Y")

        # Use utils module to generate filename and save data
        filename = utils.create_export_filename(
            account_name,
            "nacl",
            region_suffix,
            current_date
        )
        
        # Save data using the utility function
        output_path = utils.save_dataframe_to_excel(df, filename)
        
        if output_path:
            utils.log_success("AWS Network ACL data exported successfully!")
            utils.log_info(f"File location: {output_path}")
            utils.log_info(f"Export contains data from {len(regions)} AWS region(s)")
            utils.log_info(f"Total Network ACLs exported: {len(all_nacl_data)}")
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