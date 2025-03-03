#!/usr/bin/env python3
"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: StratusScan Utilities Module
Version: v1.1.0
Date: MAR-03-2025

Description:
Shared utility functions for StratusScan scripts. This module provides common
functionality such as path handling, file operations, standardized output
formatting, and account mapping that can be used across all StratusScan export scripts.
"""

import os
import sys
import datetime
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('stratusscan')

# Default empty account mappings
ACCOUNT_MAPPINGS = {}
CONFIG_DATA = {}

# Try to load configuration from config.json file
def load_config():
    """
    Load configuration from config.json file.
    
    Returns:
        tuple: (ACCOUNT_MAPPINGS, CONFIG_DATA)
    """
    global ACCOUNT_MAPPINGS, CONFIG_DATA
    
    try:
        # Get the path to config.json
        config_path = Path(__file__).parent / 'config.json'
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                CONFIG_DATA = json.load(f)
                
                # Get account mappings from config
                if 'account_mappings' in CONFIG_DATA:
                    ACCOUNT_MAPPINGS = CONFIG_DATA['account_mappings']
                    logger.debug(f"Loaded {len(ACCOUNT_MAPPINGS)} account mappings from config.json")
                
                logger.debug("Configuration loaded successfully")
        else:
            logger.warning("config.json not found. Using default configuration.")
            
            # Create a default config if it doesn't exist
            default_config = {
                "__comment": "StratusScan Configuration - Customize this file for your environment",
                "account_mappings": {},
                "agency_name": "YOUR-AGENCY",
                "default_regions": ["us-east-1", "us-west-2"],
                "resource_preferences": {
                    "ec2": {
                        "default_filter": "all", 
                        "include_stopped": True,
                        "default_region": "all"
                    },
                    "vpc": {
                        "default_export_type": "all",
                        "default_region": "all"
                    }
                }
            }
            
            # Try to save the default config
            try:
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                logger.info(f"Created default config.json at {config_path}")
                
                # Update global variables
                CONFIG_DATA = default_config
                ACCOUNT_MAPPINGS = {}
            except Exception as e:
                logger.error(f"Failed to create default config.json: {e}")
    
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
    
    return ACCOUNT_MAPPINGS, CONFIG_DATA

# Load configuration on module import
ACCOUNT_MAPPINGS, CONFIG_DATA = load_config()

def get_resource_preference(resource_type, preference, default=None):
    """
    Get a resource-specific preference from the configuration.
    
    Args:
        resource_type: Type of resource (e.g., 'ec2', 'vpc')
        preference: Preference name
        default: Default value if preference is not found
        
    Returns:
        The preference value or default
    """
    if 'resource_preferences' in CONFIG_DATA:
        resource_prefs = CONFIG_DATA['resource_preferences']
        if resource_type in resource_prefs and preference in resource_prefs[resource_type]:
            return resource_prefs[resource_type][preference]
    
    return default

def get_default_regions():
    """
    Get the default AWS regions from configuration.
    
    Returns:
        list: List of default region names
    """
    return CONFIG_DATA.get('default_regions', ['us-east-1', 'us-west-2'])

def get_agency_name():
    """
    Get the agency name from configuration.
    
    Returns:
        str: Agency name or default
    """
    return CONFIG_DATA.get('agency_name', 'YOUR-AGENCY')

def log_error(error_message, error_obj=None):
    """
    Log an error message to the console.
    
    Args:
        error_message: The error message to display
        error_obj: Optional exception object
    """
    if error_obj:
        logger.error(f"{error_message}: {str(error_obj)}")
    else:
        logger.error(error_message)

def log_warning(warning_message):
    """
    Log a warning message to the console.
    
    Args:
        warning_message: The warning message to display
    """
    logger.warning(warning_message)

def log_info(info_message):
    """
    Log an informational message to the console.
    
    Args:
        info_message: The information message to display
    """
    logger.info(info_message)

def log_success(success_message):
    """
    Log a success message to the console.
    
    Args:
        success_message: The success message to display
    """
    logger.info(f"SUCCESS: {success_message}")

def prompt_for_confirmation(message="Do you want to continue?", default=True):
    """
    Prompt the user for confirmation.
    
    Args:
        message: Message to display
        default: Default response if user just presses Enter
        
    Returns:
        bool: True if confirmed, False otherwise
    """
    default_prompt = " (Y/n): " if default else " (y/N): "
    response = input(f"{message}{default_prompt}").strip().lower()
    
    if not response:
        return default
    
    return response.lower() in ['y', 'yes']

def format_bytes(size_bytes):
    """
    Format bytes to human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted size string (e.g., "1.23 GB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

def get_current_timestamp():
    """
    Get current timestamp in a standardized format.
    
    Returns:
        str: Formatted timestamp
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def is_valid_aws_account_id(account_id):
    """
    Check if a string is a valid AWS account ID.
    
    Args:
        account_id: The account ID to check
        
    Returns:
        bool: True if valid, False otherwise
    """
    import re
    
    # AWS account IDs are 12 digits
    pattern = re.compile(r'^\d{12}config_value(key, default=None, section=None):
    """
    Get a value from the configuration.
    
    Args:
        key: Configuration key
        default: Default value if key is not found
        section: Optional section in the configuration
        
    Returns:
        The configuration value or default
    """
    if not CONFIG_DATA:
        return default
    
    try:
        if section:
            if section in CONFIG_DATA and key in CONFIG_DATA[section]:
                return CONFIG_DATA[section][key]
        else:
            if key in CONFIG_DATA:
                return CONFIG_DATA[key]
    except Exception:
        pass
    
    return default

def get_account_name(account_id, default="UNKNOWN-ACCOUNT"):
    """
    Get account name from account ID using configured mappings
    
    Args:
        account_id: The AWS account ID
        default: Default value to return if account_id is not found in mappings
        
    Returns:
        str: The account name or default value
    """
    return ACCOUNT_MAPPINGS.get(account_id, default)

def get_account_name_formatted(owner_id):
    """
    Get the formatted account name with ID from the owner ID.
    
    Args:
        owner_id: The AWS account owner ID
        
    Returns:
        str: Formatted as "ACCOUNT-NAME (ID)" if mapping exists, otherwise just the ID
    """
    if owner_id in ACCOUNT_MAPPINGS:
        return f"{ACCOUNT_MAPPINGS[owner_id]} ({owner_id})"
    return owner_id

def get_stratusscan_root():
    """
    Get the root directory of the StratusScan package.
    
    If the script using this function is in the scripts/ directory,
    this will return the parent directory. If the script is in the
    root directory, this will return that directory.
    
    Returns:
        Path: Path to the StratusScan root directory
    """
    # Get directory of the calling script
    calling_script = Path(sys.argv[0]).absolute()
    script_dir = calling_script.parent
    
    # Check if we're in a 'scripts' subdirectory
    if script_dir.name.lower() == 'scripts':
        # Return the parent (StratusScan root)
        return script_dir.parent
    else:
        # Assume we're already at the root
        return script_dir

def get_output_dir():
    """
    Get the path to the output directory and create it if it doesn't exist.
    
    Returns:
        Path: Path to the output directory
    """
    # Get StratusScan root directory
    root_dir = get_stratusscan_root()
    
    # Define the output directory path
    output_dir = root_dir / "output"
    
    # Create the directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    
    return output_dir

def get_output_filepath(filename):
    """
    Get the full path for a file in the output directory.
    
    Args:
        filename: The name of the file
        
    Returns:
        Path: Full path to the file in the output directory
    """
    return get_output_dir() / filename

def create_export_filename(account_name, resource_type, suffix="", current_date=None):
    """
    Create a standardized filename for exported data.
    
    Args:
        account_name: AWS account name
        resource_type: Type of resource being exported (e.g., "ec2", "vpc")
        suffix: Optional suffix for the filename (e.g., "running", "all")
        current_date: Date to use in the filename (defaults to today)
        
    Returns:
        str: Standardized filename with path
    """
    # Get current date if not provided
    if not current_date:
        current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Build the filename
    if suffix:
        filename = f"{account_name}-{resource_type}-{suffix}-export-{current_date}.xlsx"
    else:
        filename = f"{account_name}-{resource_type}-export-{current_date}.xlsx"
    
    return filename

def save_dataframe_to_excel(df, filename, sheet_name="Data", auto_adjust_columns=True):
    """
    Save a pandas DataFrame to an Excel file in the output directory.
    
    Args:
        df: pandas DataFrame to save
        filename: Name of the file to save
        sheet_name: Name of the sheet in Excel
        auto_adjust_columns: Whether to auto-adjust column widths
        
    Returns:
        str: Full path to the saved file
    """
    try:
        # Import pandas here to avoid dependency issues
        import pandas as pd
        
        # Get the full path
        output_path = get_output_filepath(filename)
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save to Excel
        if auto_adjust_columns:
            # Create Excel writer
            writer = pd.ExcelWriter(output_path, engine='openpyxl')
            
            # Write DataFrame to Excel
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets[sheet_name]
            for i, column in enumerate(df.columns):
                column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
                # Set a maximum column width to avoid extremely wide columns
                column_width = min(column_width, 50)
                # openpyxl column indices are 1-based
                column_letter = chr(65 + i) if i < 26 else chr(64 + i//26) + chr(65 + i%26)
                worksheet.column_dimensions[column_letter].width = column_width
            
            # Save the workbook
            writer.close()
        else:
            # Save directly without adjusting columns
            df.to_excel(output_path, sheet_name=sheet_name, index=False)
        
        logger.info(f"Data successfully exported to: {output_path}")
        
        return str(output_path)
    
    except Exception as e:
        logger.error(f"Error saving Excel file: {e}")
        
        # Try CSV as fallback
        try:
            csv_filename = filename.replace('.xlsx', '.csv')
            csv_path = get_output_filepath(csv_filename)
            
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved as CSV instead: {csv_path}")
            return str(csv_path)
            
        except Exception as csv_e:
            logger.error(f"Error saving CSV file: {csv_e}")
            return None

def save_multiple_dataframes_to_excel(dataframes_dict, filename):
    """
    Save multiple pandas DataFrames to a single Excel file with multiple sheets.
    
    Args:
        dataframes_dict: Dictionary of {sheet_name: dataframe}
        filename: Name of the file to save
        
    Returns:
        str: Full path to the saved file
    """
    try:
        # Import pandas here to avoid dependency issues
        import pandas as pd
        
        # Get the full path
        output_path = get_output_filepath(filename)
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create Excel writer
        writer = pd.ExcelWriter(output_path, engine='openpyxl')
        
        # Write each DataFrame to a separate sheet
        for sheet_name, df in dataframes_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets[sheet_name]
            for i, column in enumerate(df.columns):
                column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
                # Set a maximum column width to avoid extremely wide columns
                column_width = min(column_width, 50)
                # openpyxl column indices are 1-based
                column_letter = chr(65 + i) if i < 26 else chr(64 + i//26) + chr(65 + i%26)
                worksheet.column_dimensions[column_letter].width = column_width
        
        # Save the workbook
        writer.close()
        
        logger.info(f"Data successfully exported to: {output_path}")
        return str(output_path)
    
    except Exception as e:
        logger.error(f"Error saving Excel file: {e}")
        return None

def get_)
    return bool(pattern.match(str(account_id)))

def add_account_mapping(account_id, account_name):
    """
    Add a new account mapping to the configuration.
    
    Args:
        account_id: AWS account ID
        account_name: Account name
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_valid_aws_account_id(account_id):
        log_error(f"Invalid AWS account ID: {account_id}")
        return False
    
    try:
        # Update global dictionary
        ACCOUNT_MAPPINGS[account_id] = account_name
        
        # Update configuration file
        config_path = Path(__file__).parent / 'config.json'
        
        if config_path.exists():
            # Read current config
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Update account mappings
            if 'account_mappings' not in config:
                config['account_mappings'] = {}
            
            config['account_mappings'][account_id] = account_name
            
            # Write updated config
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            log_success(f"Added account mapping: {account_id} → {account_name}")
            return True
        else:
            log_error("config.json not found")
            return False
    
    except Exception as e:
        log_error("Failed to add account mapping", e)
        return False

def validate_aws_credentials():
    """
    Validate AWS credentials.
    
    Returns:
        tuple: (is_valid, account_id, error_message)
    """
    try:
        import boto3
        
        # Create STS client
        sts = boto3.client('sts')
        
        # Get caller identity
        response = sts.get_caller_identity()
        
        account_id = response['Account']
        return True, account_id, None
    except Exception as e:
        return False, None, str(e)

def check_aws_region_access(region):
    """
    Check if a specific AWS region is accessible.
    
    Args:
        region: AWS region name
        
    Returns:
        bool: True if accessible, False otherwise
    """
    try:
        import boto3
        
        # Try to create an EC2 client in the region
        ec2 = boto3.client('ec2', region_name=region)
        
        # Try a simple API call
        ec2.describe_regions(RegionNames=[region])
        
        return True
    except Exception:
        return False

def resource_list_to_dataframe(resource_list, columns=None):
    """
    Convert a list of dictionaries to a pandas DataFrame with specific columns.
    
    Args:
        resource_list: List of resource dictionaries
        columns: Optional list of columns to include
        
    Returns:
        DataFrame: pandas DataFrame
    """
    import pandas as pd
    
    if not resource_list:
        return pd.DataFrame()
    
    df = pd.DataFrame(resource_list)
    
    if columns:
        # Keep only specified columns that exist in the DataFrame
        existing_columns = [col for col in columns if col in df.columns]
        df = df[existing_columns]
    
    return dfconfig_value(key, default=None, section=None):
    """
    Get a value from the configuration.
    
    Args:
        key: Configuration key
        default: Default value if key is not found
        section: Optional section in the configuration
        
    Returns:
        The configuration value or default
    """
    if not CONFIG_DATA:
        return default
    
    try:
        if section:
            if section in CONFIG_DATA and key in CONFIG_DATA[section]:
                return CONFIG_DATA[section][key]
        else:
            if key in CONFIG_DATA:
                return CONFIG_DATA[key]
    except Exception:
        pass
    
    return default

def get_account_name(account_id, default="UNKNOWN-ACCOUNT"):
    """
    Get account name from account ID using configured mappings
    
    Args:
        account_id: The AWS account ID
        default: Default value to return if account_id is not found in mappings
        
    Returns:
        str: The account name or default value
    """
    return ACCOUNT_MAPPINGS.get(account_id, default)

def get_account_name_formatted(owner_id):
    """
    Get the formatted account name with ID from the owner ID.
    
    Args:
        owner_id: The AWS account owner ID
        
    Returns:
        str: Formatted as "ACCOUNT-NAME (ID)" if mapping exists, otherwise just the ID
    """
    if owner_id in ACCOUNT_MAPPINGS:
        return f"{ACCOUNT_MAPPINGS[owner_id]} ({owner_id})"
    return owner_id

def get_stratusscan_root():
    """
    Get the root directory of the StratusScan package.
    
    If the script using this function is in the scripts/ directory,
    this will return the parent directory. If the script is in the
    root directory, this will return that directory.
    
    Returns:
        Path: Path to the StratusScan root directory
    """
    # Get directory of the calling script
    calling_script = Path(sys.argv[0]).absolute()
    script_dir = calling_script.parent
    
    # Check if we're in a 'scripts' subdirectory
    if script_dir.name.lower() == 'scripts':
        # Return the parent (StratusScan root)
        return script_dir.parent
    else:
        # Assume we're already at the root
        return script_dir

def get_output_dir():
    """
    Get the path to the output directory and create it if it doesn't exist.
    
    Returns:
        Path: Path to the output directory
    """
    # Get StratusScan root directory
    root_dir = get_stratusscan_root()
    
    # Define the output directory path
    output_dir = root_dir / "output"
    
    # Create the directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    
    return output_dir

def get_output_filepath(filename):
    """
    Get the full path for a file in the output directory.
    
    Args:
        filename: The name of the file
        
    Returns:
        Path: Full path to the file in the output directory
    """
    return get_output_dir() / filename

def create_export_filename(account_name, resource_type, suffix="", current_date=None):
    """
    Create a standardized filename for exported data.
    
    Args:
        account_name: AWS account name
        resource_type: Type of resource being exported (e.g., "ec2", "vpc")
        suffix: Optional suffix for the filename (e.g., "running", "all")
        current_date: Date to use in the filename (defaults to today)
        
    Returns:
        str: Standardized filename with path
    """
    # Get current date if not provided
    if not current_date:
        current_date = datetime.datetime.now().strftime("%m.%d.%Y")
    
    # Build the filename
    if suffix:
        filename = f"{account_name}-{resource_type}-{suffix}-export-{current_date}.xlsx"
    else:
        filename = f"{account_name}-{resource_type}-export-{current_date}.xlsx"
    
    return filename

def save_dataframe_to_excel(df, filename, sheet_name="Data", auto_adjust_columns=True):
    """
    Save a pandas DataFrame to an Excel file in the output directory.
    
    Args:
        df: pandas DataFrame to save
        filename: Name of the file to save
        sheet_name: Name of the sheet in Excel
        auto_adjust_columns: Whether to auto-adjust column widths
        
    Returns:
        str: Full path to the saved file
    """
    try:
        # Import pandas here to avoid dependency issues
        import pandas as pd
        
        # Get the full path
        output_path = get_output_filepath(filename)
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save to Excel
        if auto_adjust_columns:
            # Create Excel writer
            writer = pd.ExcelWriter(output_path, engine='openpyxl')
            
            # Write DataFrame to Excel
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets[sheet_name]
            for i, column in enumerate(df.columns):
                column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
                # Set a maximum column width to avoid extremely wide columns
                column_width = min(column_width, 50)
                # openpyxl column indices are 1-based
                column_letter = chr(65 + i) if i < 26 else chr(64 + i//26) + chr(65 + i%26)
                worksheet.column_dimensions[column_letter].width = column_width
            
            # Save the workbook
            writer.close()
        else:
            # Save directly without adjusting columns
            df.to_excel(output_path, sheet_name=sheet_name, index=False)
        
        logger.info(f"Data successfully exported to: {output_path}")
        
        return str(output_path)
    
    except Exception as e:
        logger.error(f"Error saving Excel file: {e}")
        
        # Try CSV as fallback
        try:
            csv_filename = filename.replace('.xlsx', '.csv')
            csv_path = get_output_filepath(csv_filename)
            
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved as CSV instead: {csv_path}")
            return str(csv_path)
            
        except Exception as csv_e:
            logger.error(f"Error saving CSV file: {csv_e}")
            return None

def save_multiple_dataframes_to_excel(dataframes_dict, filename):
    """
    Save multiple pandas DataFrames to a single Excel file with multiple sheets.
    
    Args:
        dataframes_dict: Dictionary of {sheet_name: dataframe}
        filename: Name of the file to save
        
    Returns:
        str: Full path to the saved file
    """
    try:
        # Import pandas here to avoid dependency issues
        import pandas as pd
        
        # Get the full path
        output_path = get_output_filepath(filename)
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create Excel writer
        writer = pd.ExcelWriter(output_path, engine='openpyxl')
        
        # Write each DataFrame to a separate sheet
        for sheet_name, df in dataframes_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets[sheet_name]
            for i, column in enumerate(df.columns):
                column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
                # Set a maximum column width to avoid extremely wide columns
                column_width = min(column_width, 50)
                # openpyxl column indices are 1-based
                column_letter = chr(65 + i) if i < 26 else chr(64 + i//26) + chr(65 + i%26)
                worksheet.column_dimensions[column_letter].width = column_width
        
        # Save the workbook
        writer.close()
        
        logger.info(f"Data successfully exported to: {output_path}")
        return str(output_path)
    
    except Exception as e:
        logger.error(f"Error saving Excel file: {e}")
        return None

def get_