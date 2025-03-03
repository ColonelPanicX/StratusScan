#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Trusted Advisor Cost Optimization Export
Version: v1.0.1
Date: FEB-28-2025

Description:
This script exports AWS Trusted Advisor Cost Optimization 
recommendations to an Excel file with a summary tab and 
detailed tabs for each cost saving opportunity.

"""

import os
import sys
import json
import datetime
import boto3
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

# Define the cost optimization check IDs
COST_OPTIMIZATION_CHECKS = {
    "Qch7DwouX1": "Low Utilization Amazon EC2 Instances",
    "djGHe3YM57": "Amazon RDS Idle DB Instances",
    "Ti39halfu8": "Underutilized Amazon EBS Volumes",
    "a2jU9xbpdD": "Underutilized Amazon Redshift Clusters",
    "G31sQ1E9U": "Unassociated Elastic IP Addresses",
    "iqdCTZKCUp": "Idle Load Balancers",
    "DAvU99Dc4C": "Underutilized Amazon EBS Volumes with IOPS",
    "Z4AUBRNSmz": "Underutilized Amazon Redshift Reserved Nodes",
    "PUQNanKh2f": "Amazon EC2 Reserved Instance Lease Expiration",
    "rQRjQHDRMi": "Amazon EC2 Reserved Instances Optimization",
    "I13nqtS9KM": "AWS Lambda Functions Using Deprecated Runtimes",
    "jEKWUjrcr5": "Amazon S3 Bucket Versioning",
    "7ujbJOwtK2": "AWS CloudFront Content Delivery Optimization",
    "G7HW2saBrz": "Amazon RDS Multi-AZ",
    "R365s2Qddf": "Amazon EC2 to Amazon RDS MySQL"
}

def check_and_install_dependencies():
    """
    Check if required dependencies are installed and offer to install them if not.
    """
    required_packages = ['pandas', 'openpyxl', 'xlsxwriter', 'tabulate']
    missing_packages = []
    
    # Check for each required package
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    # If there are missing packages, prompt the user to install them
    if missing_packages:
        print("The following dependencies are required but not installed:")
        for package in missing_packages:
            print(f"  - {package}")
        
        user_input = input("Would you like to install these packages? (y/n): ").strip().lower()
        
        if user_input == 'y':
            print("Installing required packages...")
            for package in missing_packages:
                print(f"Installing {package}...")
                os.system(f"{sys.executable} -m pip install {package}")
            print("All required packages have been installed.")
        else:
            print("Required packages were not installed. Script cannot continue.")
            sys.exit(1)

    # Import required packages
    import pandas as pd
    global pd

def get_account_id():
    """
    Get the AWS account ID of the current session.
    
    Returns:
        str: The AWS account ID
    """
    try:
        # Create a STS client
        sts_client = boto3.client('sts')
        
        # Get the current account ID
        account_id = sts_client.get_caller_identity()["Account"]
        
        return account_id
    except ClientError as e:
        print(f"Error getting account ID: {e}")
        sys.exit(1)

def get_trusted_advisor_checks():
    """
    Get all Trusted Advisor checks related to cost optimization.
    
    Returns:
        list: List of Trusted Advisor check results
    """
    try:
        # Create a Support client (requires Business or Enterprise Support plan)
        support_client = boto3.client('support')
        
        # Get all Trusted Advisor checks
        response = support_client.describe_trusted_advisor_checks(language='en')
        
        # Filter to only cost optimization checks
        cost_checks = [check for check in response['checks'] if check['category'] == 'cost_optimizing']
        
        return cost_checks
    except ClientError as e:
        if 'SubscriptionRequiredException' in str(e):
            print("Error: AWS Business or Enterprise Support plan is required to access Trusted Advisor API.")
        else:
            print(f"Error accessing Trusted Advisor checks: {e}")
        sys.exit(1)

def get_check_result(check_id):
    """
    Get the detailed results for a specific Trusted Advisor check.
    
    Args:
        check_id (str): The ID of the Trusted Advisor check
        
    Returns:
        dict: The detailed results of the check
    """
    try:
        # Create a Support client
        support_client = boto3.client('support')
        
        # Get the check result
        response = support_client.describe_trusted_advisor_check_result(
            checkId=check_id,
            language='en'
        )
        
        return response['result']
    except ClientError as e:
        print(f"Error getting check result for {check_id}: {e}")
        return None

def get_all_check_results():
    """
    Get results for all cost optimization checks.
    
    Returns:
        dict: A dictionary with check details and results
    """
    # Get all cost optimization checks
    checks = get_trusted_advisor_checks()
    
    # Get results for each check
    results = {}
    for check in checks:
        check_id = check['id']
        check_name = check['name']
        print(f"Fetching results for: {check_name}")
        
        result = get_check_result(check_id)
        if result:
            results[check_id] = {
                'name': check_name,
                'description': check['description'],
                'result': result
            }
    
    return results

def extract_savings(metadata, index):
    """
    Safely extract savings value from metadata at the given index.
    
    Args:
        metadata (list): The metadata list
        index (int): Index to extract from
        
    Returns:
        float: The extracted savings value, or 0 if not found
    """
    try:
        if len(metadata) > index and metadata[index] and isinstance(metadata[index], str):
            if "$" in metadata[index]:
                savings_text = metadata[index].replace("$", "").replace(",", "")
                return float(savings_text)
    except (ValueError, IndexError, AttributeError):
        pass
    return 0

def process_check_results(results):
    """
    Process the check results into a format suitable for Excel.
    
    Args:
        results (dict): The check results
        
    Returns:
        tuple: (summary_df, detail_dfs) containing the summary dataframe and detail dataframes
    """
    import pandas as pd
    
    # Create a list to store summary data
    summary_data = []
    
    # Dictionary to store detail dataframes for each check
    detail_dfs = {}
    
    # Total estimated savings
    total_savings = 0
    
    # Process each check result
    for check_id, check_info in results.items():
        check_name = check_info['name']
        result = check_info['result']
        
        # Skip if there are no resources to optimize (flaggedResources is empty)
        if not result.get('flaggedResources', []):
            continue
        
        # Calculate estimated savings
        estimated_savings = 0
        resources_count = len(result.get('flaggedResources', []))
        
        # Extract detail data for this check
        detail_data = []
        
        for resource in result.get('flaggedResources', []):
            # Extract metadata fields
            metadata = resource.get('metadata', [])
            
            # Process metadata based on the check type
            resource_metadata = {}
            
            # Process the metadata fields (skip index 0 which is typically Region)
            for i, field in enumerate(metadata):
                if i == 0:  # Skip the first metadata field (metadata_0)
                    continue
                
                # Get the field name
                field_name = result.get('metadata', [])[i] if i < len(result.get('metadata', [])) else f"Field_{i}"
                
                # Special column mapping for "Idle Load Balancers" (check ID: iqdCTZKCUp)
                if check_id == "iqdCTZKCUp":
                    if i == 2:
                        field_name = "Description"
                    elif i == 3:
                        field_name = "Potential Cost Savings"
                
                # Special column mapping for "Low Utilization Amazon EC2 Instances" (check ID: Qch7DwouX1)
                elif check_id == "Qch7DwouX1":
                    if i == 4:
                        field_name = "Estimated Monthly Savings"
                
                resource_metadata[field_name] = field
            
            # Extract resource savings based on check type
            resource_savings = 0
            
            if check_id == "Qch7DwouX1":  # Low Utilization EC2
                resource_savings = extract_savings(metadata, 4)  # Changed from 5 to 4 based on updated mapping
            elif check_id == "djGHe3YM57":  # RDS Idle Instances
                resource_savings = extract_savings(metadata, 3)
            elif check_id == "Ti39halfu8":  # Underutilized EBS
                resource_savings = extract_savings(metadata, 6)
            elif check_id == "iqdCTZKCUp":  # Idle Load Balancers
                resource_savings = extract_savings(metadata, 3)
            else:
                # Generic approach to find a savings field
                for field in metadata:
                    if field and isinstance(field, str) and "$" in field:
                        try:
                            savings_text = field.replace("$", "").replace(",", "")
                            resource_savings = float(savings_text)
                            break
                        except (ValueError, AttributeError):
                            pass
            
            # Add to estimated savings total
            if resource_savings > 0:
                estimated_savings += resource_savings
            
            # Create detail row for this resource
            detail_row = {
                'Status': resource.get('status', 'Unknown'),
                'Estimated Monthly Savings': f"${resource_savings:.2f}" if resource_savings > 0 else "Unknown"
            }
            
            # Add all metadata fields
            detail_row.update(resource_metadata)
            
            detail_data.append(detail_row)
        
        # Create detail dataframe for this check
        if detail_data:
            detail_df = pd.DataFrame(detail_data)
            detail_dfs[check_name] = detail_df
            
            # Add to summary data
            summary_data.append({
                'Check ID': check_id,
                'Check Name': check_name,
                'Resources to Optimize': resources_count,
                'Estimated Monthly Savings': f"${estimated_savings:.2f}" if estimated_savings > 0 else "Unknown"
            })
            
            # Add to total savings
            if estimated_savings > 0:
                total_savings += estimated_savings
    
    # Add total to summary data
    summary_data.append({
        'Check ID': 'TOTAL',
        'Check Name': 'All Checks',
        'Resources to Optimize': sum(item['Resources to Optimize'] for item in summary_data),
        'Estimated Monthly Savings': f"${total_savings:.2f}"
    })
    
    # Create summary dataframe
    summary_df = pd.DataFrame(summary_data)
    
    return summary_df, detail_dfs

def export_to_excel(summary_df, detail_dfs, account_name):
    """
    Export the data to an Excel file with multiple tabs.
    
    Args:
        summary_df (DataFrame): The summary data
        detail_dfs (dict): Dictionary of detail dataframes
        account_name (str): The name of the account
        
    Returns:
        str: The path to the saved Excel file
    """
    import pandas as pd
    
    # Get current date for filename
    current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Create the full output path
    filename = output_dir / f"{account_name}-ta-cost-optimization-export-{current_date}.xlsx"
    
    # Create a Pandas Excel writer
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    
    # Write the summary dataframe to the Excel file
    summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    # Get the workbook and the summary worksheet
    workbook = writer.book
    summary_worksheet = writer.sheets['Summary']
    
    # Add formatting to the summary sheet
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#D9E1F2',
        'border': 1
    })
    
    # Apply formatting to header row
    for col_num, col_name in enumerate(summary_df.columns):
        summary_worksheet.write(0, col_num, col_name, header_format)
    
    # Set column widths for summary
    summary_worksheet.set_column('A:A', 15)  # Check ID
    summary_worksheet.set_column('B:B', 40)  # Check Name
    summary_worksheet.set_column('C:C', 20)  # Resources to Optimize
    summary_worksheet.set_column('D:D', 25)  # Estimated Monthly Savings
    
    # Format the total row
    total_format = workbook.add_format({
        'bold': True,
        'bg_color': '#FFEB9C',
        'border': 1
    })
    
    # Apply total formatting to the last row
    last_row = len(summary_df)
    for col_num, col_name in enumerate(summary_df.columns):
        summary_worksheet.write(last_row, col_num, summary_df.iloc[-1].iloc[col_num], total_format)
    
    # Write each detail dataframe to a separate sheet
    for check_name, detail_df in detail_dfs.items():
        # Create a valid sheet name (Excel has a 31 character limit and can't have special characters)
        sheet_name = check_name[:31].replace('/', '-').replace('\\', '-').replace('?', '').replace('*', '')
        
        # Write the detail dataframe
        detail_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Get the worksheet
        worksheet = writer.sheets[sheet_name]
        
        # Apply formatting to header row
        for col_num, col_name in enumerate(detail_df.columns):
            worksheet.write(0, col_num, col_name, header_format)
        
        # Set column widths based on content
        for i, col in enumerate(detail_df.columns):
            # Set a sensible default width
            col_width = 15
            
            # Adjust for column name length
            col_width = max(col_width, len(str(col)) + 2)
            
            # Sample some values to determine width
            for j in range(min(10, len(detail_df))):
                cell_value = detail_df.iloc[j, i]
                if cell_value:
                    col_width = max(col_width, len(str(cell_value)) + 2)
            
            # Cap the width to avoid excessively wide columns
            col_width = min(col_width, 50)
            
            worksheet.set_column(i, i, col_width)
    
    # Save the Excel file
    writer.close()
    
    print(f"Data has been exported to: {filename}")
    return filename

def main():
    """
    Main function to execute the script.
    """
    # Check and install dependencies
    check_and_install_dependencies()
    
    # Import pandas
    import pandas as pd
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")    
    print("====================================================================")
    print("AWS TRUSTED ADVISOR - COST OPTIMIZATION DATA EXPORT")
    print("====================================================================")
    
    # Get account ID
    account_id = get_account_id()
    
    # Get account name from mapping or use account ID if not mapped
    account_name = utils.get_account_name(account_id, default=account_id)
    
    print(f"Account ID: {account_id}")
    print(f"Account Name: {account_name}")
    print("====================================================================")
    
    print("Fetching Trusted Advisor Cost Optimization checks...")
    results = get_all_check_results()
    
    if not results:
        print("No cost optimization results found or error occurred.")
        sys.exit(1)
    
    print("Processing check results...")
    summary_df, detail_dfs = process_check_results(results)
    
    if summary_df.empty:
        print("No resources to optimize were found.")
        sys.exit(0)
    
    print("Exporting results to Excel...")
    filename = export_to_excel(summary_df, detail_dfs, account_name)
    
    print("====================================================================")
    print(f"Full details available in: {filename}")
    print("====================================================================")


if __name__ == "__main__":
    main()
