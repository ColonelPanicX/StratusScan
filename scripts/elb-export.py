#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Elastic Load Balancer Data Export
Version: v1.1.0
Date: MAR-04-2025

Description:
This script queries for Load Balancers across all regions or a specific region and 
exports the list to a single Excel spreadsheet.

"""

import boto3
import pandas as pd
import datetime
import os
import sys
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

def print_title_screen():
    """
    Prints a formatted title screen with script information
    
    Returns:
        str: The account name
    """
    # Get the AWS account ID using STS
    try:
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity()['Account']
        # Get the corresponding account name from utils module
        account_name = utils.get_account_name(account_id, default="UNKNOWN-ACCOUNT")
    except Exception as e:
        print(f"Warning: Unable to determine AWS account ID: {str(e)}")
        account_id = "UNKNOWN"
        account_name = "UNKNOWN-ACCOUNT"
    
    # Print the title screen with account information
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")    
    print("====================================================================")
    print("AWS ELB INVENTORY EXPORT SCRIPT")
    print("====================================================================")
    print("Version: v1.1.0                                 Date: MAR-04-2025")
    print("====================================================================")
    print(f"Account ID: {account_id}")
    print(f"Account Name: {account_name}")
    print("====================================================================")
    
    return account_name

def check_dependencies():
    """
    Checks if required dependencies are installed and offers to install them
    
    Returns:
        bool: True if all dependencies are installed or successfully installed,
              False otherwise
    """
    required_packages = ['pandas', 'openpyxl']
    missing_packages = []
    
    # Check which required packages are missing
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is already installed")
        except ImportError:
            missing_packages.append(package)
    
    # If there are missing packages, prompt the user to install them
    if missing_packages:
        print(f"\nMissing dependencies: {', '.join(missing_packages)}")
        install_choice = input("Do you want to install the missing dependencies? (y/n): ").lower().strip()
        
        if install_choice == 'y':
            import subprocess
            for package in missing_packages:
                print(f"Installing {package}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"{package} installed successfully.")
                except Exception as e:
                    print(f"Error installing {package}: {e}")
                    print("Please install it manually with: pip install " + package)
                    return False
            return True
        else:
            print("Script cannot continue without required dependencies. Exiting.")
            return False
    
    return True

def get_all_regions():
    """
    Get a list of all available AWS regions
    
    Returns:
        list: List of region names
    """
    try:
        # Create an EC2 client to get all available regions
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
        return regions
    except Exception as e:
        print(f"Error getting regions: {e}")
        # Return a default list of common regions if we can't get the complete list
        return [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'ca-central-1', 'eu-west-1', 'eu-west-2', 'eu-central-1',
            'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-south-1'
        ]

def is_valid_region(region_name):
    """
    Check if a region name is valid
    
    Args:
        region_name (str): The region name to check
        
    Returns:
        bool: True if valid, False otherwise
    """
    all_regions = get_all_regions()
    return region_name in all_regions

def get_security_group_names(security_group_ids, region):
    """
    Get security group names for the given IDs
    
    Args:
        security_group_ids (list): List of security group IDs
        region (str): AWS region
        
    Returns:
        dict: Mapping of security group IDs to names
    """
    if not security_group_ids:
        return {}
        
    ec2 = boto3.client('ec2', region_name=region)
    sg_mapping = {}
    
    try:
        # Fetch security group information
        response = ec2.describe_security_groups(GroupIds=security_group_ids)
        
        # Create a mapping of security group IDs to names
        for sg in response['SecurityGroups']:
            sg_mapping[sg['GroupId']] = sg['GroupName']
            
    except Exception as e:
        print(f"Warning: Unable to fetch security group names: {str(e)}")
    
    return sg_mapping

def get_classic_load_balancers(region):
    """
    Get information about Classic Load Balancers in the specified region
    
    Args:
        region (str): AWS region
        
    Returns:
        list: List of dictionaries containing Classic Load Balancer information
    """
    elb_data = []
    
    try:
        # Create an ELB client for the specified region
        elb = boto3.client('elb', region_name=region)
        
        # Describe all Classic Load Balancers
        response = elb.describe_load_balancers()
        
        for lb in response.get('LoadBalancerDescriptions', []):
            # Get security group names for the security group IDs
            sg_ids = lb.get('SecurityGroups', [])
            sg_mapping = get_security_group_names(sg_ids, region)
            
            # Format security groups as "sg-name (sg-id), ..."
            security_groups = []
            for sg_id in sg_ids:
                sg_name = sg_mapping.get(sg_id, "Unknown")
                security_groups.append(f"{sg_name} ({sg_id})")
            
            # Format availability zones as "subnet-id (az), ..."
            availability_zones = []
            for az in lb.get('AvailabilityZones', []):
                availability_zones.append(f"{az}")
            
            # Add subnets if available (VPC Classic ELB)
            for subnet_id in lb.get('Subnets', []):
                # For VPC Classic ELBs, we need to get the AZ for each subnet
                ec2 = boto3.client('ec2', region_name=region)
                subnet_response = ec2.describe_subnets(SubnetIds=[subnet_id])
                subnet_az = subnet_response['Subnets'][0]['AvailabilityZone']
                availability_zones.append(f"{subnet_id} ({subnet_az})")
            
            # Get creation time
            created_time = lb.get('CreatedTime', datetime.datetime.now())
            
            # Add load balancer data to the list
            elb_data.append({
                'Region': region,
                'Name': lb.get('LoadBalancerName', ''),
                'DNS Name': lb.get('DNSName', ''),
                'VPC ID': lb.get('VPCId', 'N/A'),
                'Availability Zones': ', '.join(availability_zones),
                'Type': 'Classic',
                'Date Created': created_time.strftime('%Y-%m-%d'),
                'Security Groups': ', '.join(security_groups) if security_groups else 'N/A'
            })
            
    except Exception as e:
        print(f"Warning: Unable to fetch Classic Load Balancers in {region}: {str(e)}")
    
    return elb_data

def get_application_network_load_balancers(region):
    """
    Get information about Application and Network Load Balancers in the specified region
    
    Args:
        region (str): AWS region
        
    Returns:
        list: List of dictionaries containing ALB/NLB information
    """
    elb_data = []
    
    try:
        # Create an ELBv2 client for the specified region
        elbv2 = boto3.client('elbv2', region_name=region)
        
        # Describe all ALBs and NLBs
        response = elbv2.describe_load_balancers()
        
        for lb in response.get('LoadBalancers', []):
            # Get load balancer type
            lb_type = lb.get('Type', 'Unknown')
            
            # Get security group names for ALBs (NLBs don't have security groups)
            sg_ids = lb.get('SecurityGroups', [])
            security_groups = []
            
            if sg_ids:
                sg_mapping = get_security_group_names(sg_ids, region)
                for sg_id in sg_ids:
                    sg_name = sg_mapping.get(sg_id, "Unknown")
                    security_groups.append(f"{sg_name} ({sg_id})")
            
            # Get subnet information
            availability_zones = []
            for az_info in lb.get('AvailabilityZones', []):
                subnet_id = az_info.get('SubnetId', '')
                zone_name = az_info.get('ZoneName', '')
                availability_zones.append(f"{subnet_id} ({zone_name})")
            
            # Get creation time
            created_time = lb.get('CreatedTime', datetime.datetime.now())
            
            # Add load balancer data to the list
            elb_data.append({
                'Region': region,
                'Name': lb.get('LoadBalancerName', ''),
                'DNS Name': lb.get('DNSName', ''),
                'VPC ID': lb.get('VpcId', 'N/A'),
                'Availability Zones': ', '.join(availability_zones),
                'Type': lb_type,
                'Date Created': created_time.strftime('%Y-%m-%d'),
                'Security Groups': ', '.join(security_groups) if security_groups else 'N/A'
            })
            
    except Exception as e:
        print(f"Warning: Unable to fetch ALBs/NLBs in {region}: {str(e)}")
    
    return elb_data

def main():
    """
    Main function to run the script
    """
    # Print the title screen and get the account name
    account_name = print_title_screen()
    
    # Check for required dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Get region preference from user
    print("\nWould you like the information for all regions or a specific region?")
    region_choice = input("If all, write \"all\", or if a specific region, write the region's name (ex. us-east-1): ").lower()
    
    # Determine regions to scan
    if region_choice == "all":
        print("\nRetrieving all AWS regions...")
        regions = get_all_regions()
        region_suffix = ""
        print(f"Found {len(regions)} regions to scan.")
    else:
        if not is_valid_region(region_choice):
            print(f"Warning: '{region_choice}' is not a valid AWS region. Please check the region name.")
            print("Available regions:")
            for region in get_all_regions():
                print(f"  {region}")
            sys.exit(1)
            
        regions = [region_choice]
        region_suffix = f"-{region_choice}"
        print(f"\nScanning only the {region_choice} region.")
    
    # Initialize a list to store all ELB data
    all_elb_data = []
    
    # Iterate through each region
    for region in regions:
        print(f"\nProcessing region: {region}")
        
        # Get Classic Load Balancers
        print(f"  Fetching Classic Load Balancers...")
        classic_elbs = get_classic_load_balancers(region)
        print(f"  Found {len(classic_elbs)} Classic Load Balancers.")
        all_elb_data.extend(classic_elbs)
        
        # Get Application and Network Load Balancers
        print(f"  Fetching Application and Network Load Balancers...")
        elbv2s = get_application_network_load_balancers(region)
        print(f"  Found {len(elbv2s)} Application and Network Load Balancers.")
        all_elb_data.extend(elbv2s)
    
    # If no ELBs found, exit
    if not all_elb_data:
        print("\nNo Elastic Load Balancers found in any region.")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(all_elb_data)
    
    # Sort by Region, Type, and Name
    df = df.sort_values(by=['Region', 'Type', 'Name'])
    
    # Generate filename with current date
    current_date = datetime.datetime.now().strftime('%m.%d.%Y')
    
    # Use utils to create filename and ensure output directory exists
    filename = utils.create_export_filename(
        account_name, 
        "elb", 
        region_suffix, 
        current_date
    )
    
    # Export to Excel using utils
    output_path = utils.save_dataframe_to_excel(df, filename)
    
    if output_path:
        print(f"\nExport complete! File saved as: {output_path}")
        print(f"Found a total of {len(all_elb_data)} Elastic Load Balancers.")
    else:
        print("\nError: Failed to save the Excel file.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        sys.exit(1)
