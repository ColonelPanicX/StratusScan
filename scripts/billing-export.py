#!/usr/bin/env python3

"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: AWS Account Billing Data Export
Version: v1.0.1
Date: FEB-28-2025

Description:
Exports AWS billing data for specified time periods (monthly or yearly), 
organized by service and associated cost.

"""

import os
import sys
import datetime
import re
import boto3
from dateutil.relativedelta import relativedelta
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

# Check if required modules are installed, and offer to install them if not
required_modules = ['pandas', 'openpyxl']
missing_modules = []

for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        missing_modules.append(module)

if missing_modules:
    print(f"The following required modules are missing: {', '.join(missing_modules)}")
    install_choice = input("Would you like to install them? ('y' for yes, 'n' for no): ")
    
    if install_choice.lower() == 'y':
        for module in missing_modules:
            print(f"Installing {module}...")
            os.system(f"pip install {module}")
            print(f"{module} installed successfully.")
    else:
        print("Required modules are not installed. Exiting script.")
        sys.exit(1)

# Now import the modules after ensuring they're installed
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

def get_account_id():
    """
    Get the current AWS account ID using the STS service.
    
    Returns:
        str: The AWS account ID
    """
    # Create an STS client to get the account ID
    sts_client = boto3.client('sts')
    
    # Get the caller identity which includes the account ID
    response = sts_client.get_caller_identity()
    
    # Extract and return the account ID
    return response['Account']

def get_account_name(account_id):
    """
    Get the account name based on the account ID using the utility function.
    
    Args:
        account_id (str): The AWS account ID
        
    Returns:
        str: The account name or 'Unknown' if not found
    """
    # Use the utility function to get the account name
    return utils.get_account_name(account_id, default="Unknown")

def validate_date_input(date_input):
    """
    Validate user input for year or month-year.
    
    Args:
        date_input (str): User input string
        
    Returns:
        tuple: (is_valid, is_year_only, start_date, end_date)
    """
    # Define regex patterns for year and month-year formats
    year_pattern = r'^\d{4}$'  # YYYY
    month_year_pattern = r'^(0[1-9]|1[0-2])-\d{4}$'  # MM-YYYY
    
    if re.match(year_pattern, date_input):
        # Year format (YYYY)
        year = int(date_input)
        start_date = datetime.datetime(year, 1, 1)
        end_date = datetime.datetime(year, 12, 31)
        return True, True, start_date, end_date
    
    elif re.match(month_year_pattern, date_input):
        # Month-Year format (MM-YYYY)
        month, year = date_input.split('-')
        month = int(month)
        year = int(year)
        
        start_date = datetime.datetime(year, month, 1)
        # Calculate the last day of the month
        if month == 12:
            end_date = datetime.datetime(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.datetime(year, month + 1, 1) - datetime.timedelta(days=1)
        
        return True, False, start_date, end_date
    
    else:
        return False, None, None, None

def get_billing_data(start_date, end_date):
    """
    Get billing data from AWS Cost Explorer API.
    
    Args:
        start_date (datetime): Start date
        end_date (datetime): End date
        
    Returns:
        dict: Billing data organized by month and service
    """
    # Convert dates to string format required by AWS API
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Create a Cost Explorer client
    ce_client = boto3.client('ce')
    
    # Use the cost explorer API to get cost and usage data
    response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date_str,
            'End': end_date_str
        },
        Granularity='MONTHLY',
        Metrics=['BlendedCost'],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            }
        ]
    )
    
    # Organize the data by month and service
    billing_data = {}
    
    for result in response['ResultsByTime']:
        # Extract the month from the time period
        period_start = result['TimePeriod']['Start']
        month = datetime.datetime.strptime(period_start, '%Y-%m-%d').strftime('%Y-%m')
        
        # Initialize the month in the billing data if not already present
        if month not in billing_data:
            billing_data[month] = {}
        
        # Process each service and its cost
        for group in result['Groups']:
            service_name = group['Keys'][0]
            cost = float(group['Metrics']['BlendedCost']['Amount'])
            
            # Add the service cost to the month data
            billing_data[month][service_name] = cost
    
    return billing_data

def create_excel_report(billing_data, output_path):
    """
    Create an Excel report with monthly billing data.
    
    Args:
        billing_data (dict): Billing data organized by month and service
        output_path (str): Path to save the Excel file
    """
    # Create a new workbook
    wb = Workbook()
    
    # Remove the default sheet
    default_sheet = wb.active
    wb.remove(default_sheet)
    
    # Define styles
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
    
    # Sort months chronologically
    sorted_months = sorted(billing_data.keys())
    
    # Process each month
    for month in sorted_months:
        # Create a sheet for the month
        sheet_name = datetime.datetime.strptime(month, '%Y-%m').strftime('%b %Y')
        ws = wb.create_sheet(sheet_name)
        
        # Create headers
        ws['A1'] = 'Service'
        ws['B1'] = 'Cost (USD)'
        
        # Apply header styles
        ws['A1'].font = header_font
        ws['B1'].font = header_font
        ws['A1'].fill = header_fill
        ws['B1'].fill = header_fill
        
        # Get monthly data
        month_data = billing_data[month]
        
        # Sort services by cost (descending)
        sorted_services = sorted(month_data.items(), key=lambda x: x[1], reverse=True)
        
        # Add data rows
        row = 2
        total_cost = 0
        
        for service, cost in sorted_services:
            ws[f'A{row}'] = service
            ws[f'B{row}'] = cost
            ws[f'B{row}'].number_format = '$#,##0.00'
            total_cost += cost
            row += 1
        
        # Add total row
        row += 1
        ws[f'A{row}'] = 'Total'
        ws[f'A{row}'].font = header_font
        ws[f'B{row}'] = total_cost
        ws[f'B{row}'].font = header_font
        ws[f'B{row}'].number_format = '$#,##0.00'
        
        # Adjust column widths
        for col in range(1, 3):
            column_letter = get_column_letter(col)
            max_length = 0
            for cell in ws[column_letter]:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            adjusted_width = max_length + 2
            ws.column_dimensions[column_letter].width = adjusted_width
    
    # Save the workbook
    wb.save(output_path)
    print(f"Excel report saved as: {output_path}")

def main():
    """
    Main function to run the script.
    """
    print("====================================================================")
    print("                  AWS RESOURCE SCANNER                              ")
    print("====================================================================")
    print("AWS ACCOUNT BILLING DATA EXPORT")
    print("====================================================================")
    
    # Get current account info
    account_id = get_account_id()
    account_name = get_account_name(account_id)
    
    print(f"Current AWS Account: {account_id} ({account_name})")
    
    # Get user input for date range
    while True:
        date_input = input("Indicate a specific year (ex. \"2024\") or a specific month (ex. \"01-2025\"): ")
        is_valid, is_year_only, start_date, end_date = validate_date_input(date_input)
        
        if is_valid:
            break
        else:
            print("Invalid input format. Please try again.")
    
    print(f"Fetching billing data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
    
    # Get billing data
    billing_data = get_billing_data(start_date, end_date)
    
    # Determine output file name
    if is_year_only:
        date_suffix = start_date.strftime('%Y')
    else:
        date_suffix = start_date.strftime('%m-%Y')
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Create the full output path
    output_file = output_dir / f"{account_name}-billing-{date_suffix}.xlsx"
    
    # Create Excel report
    create_excel_report(billing_data, output_file)
    
    print("Billing data export completed successfully.")

if __name__ == "__main__":
    main()
