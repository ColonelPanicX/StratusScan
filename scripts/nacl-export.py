#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Network ACL (NACL) Data Export
Version: v1.0.0
Date: MAR-05-2025

Description:
This script exports Network ACL (NACL) information from all AWS regions or a specific region,
including NACL ID, VPC ID, inbound/outbound rules, subnet associations, and tags.
The data is exported to an Excel file with standardized naming convention.
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
    """
    required_packages = ['pandas', 'openpyxl']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is already installed")
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
                    print(f"✓ Successfully installed {package}")
                except Exception as e:
                    print(f"Error installing {package}: {e}")
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
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("AWS NETWORK ACL (NACL) DATA EXPORT TOOL")
    print("====================================================================")
    print("Version: v1.0.0                                 Date: MAR-05-2025")
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

def get_all_regions():
    """
    Get a list of all available AWS regions.
    
    Returns:
        list: List of region names
    """
    try:
        # Create an EC2 client to get region information
        ec2_client = boto3.client('ec2')
        # Describe all regions using the EC2 DescribeRegions API call
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        return regions
    except Exception as e:
        print(f"Error getting regions: {e}")
        return []

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
    Get Network ACL information for a specific region.
    
    Args:
        region: AWS region name
        
    Returns:
        list: List of dictionaries with NACL information
    """
    nacl_data = []
    
    try:
        # Create EC2 client for the specified region
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
                'Tags': tags_str
            }
            
            nacl_data.append(nacl_entry)
            
    except Exception as e:
        print(f"Error collecting NACL data in region {region}: {e}")
    
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
        
        # Ask for region selection
        print("\nChoose region option:")
        print("1. All regions")
        print("2. Specific region")
        
        while True:
            region_choice = input("Enter your choice (1 or 2): ").strip()
            if region_choice in ["1", "2"]:
                break
            print("Invalid choice. Please enter 1 or 2.")
        
        # Determine regions to scan
        if region_choice == "1":
            print("\nRetrieving all AWS regions...")
            regions = get_all_regions()
            if not regions:
                print("Error: No AWS regions found. Please check your AWS credentials and permissions.")
                sys.exit(1)
            print(f"Found {len(regions)} regions to scan.")
            region_suffix = ""
        else:
            # Ask for a specific region
            region_input = input("\nEnter the region name (e.g., us-east-1): ").strip()
            all_regions = get_all_regions()
            
            if region_input in all_regions:
                regions = [region_input]
                print(f"\nScanning region: {region_input}")
                region_suffix = f"-{region_input}"
            else:
                print(f"Warning: '{region_input}' does not appear to be a valid region. Defaulting to all regions.")
                regions = all_regions
                print(f"Found {len(regions)} regions to scan.")
                region_suffix = ""
        
        # Collect NACL data from all specified regions
        all_nacl_data = []
        
        print("\nCollecting Network ACL data...")
        for i, region in enumerate(regions, 1):
            print(f"Processing region {i}/{len(regions)}: {region}")
            region_data = get_nacl_data(region)
            all_nacl_data.extend(region_data)
            print(f"  Found {len(region_data)} NACLs in {region}")
            
            # Add a small delay to avoid API throttling
            time.sleep(0.5)
        
        # Check if we found any NACLs
        if not all_nacl_data:
            print("\nNo Network ACLs found in any region. Exiting...")
            sys.exit(0)
        
        # Create DataFrame
        print("\nCreating report...")
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
            print(f"\nData exported successfully to: {output_path}")
            print(f"Found a total of {len(all_nacl_data)} Network ACLs across {len(regions)} regions.")
            print("\nScript execution completed.")
        else:
            print("\nError exporting data. Please check the logs.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
