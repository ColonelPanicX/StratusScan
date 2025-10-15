#!/usr/bin/env python3
"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: StratusScan Utilities Module
Version: v1.1.0
Date: AUG-19-2025

Description:
Shared utility functions for StratusScan scripts optimized for AWS Commercial
environment. This module provides common functionality such as
path handling, file operations, standardized output formatting, account mapping,
and region and partition handling.

Features:
- Updated default regions to standard AWS regions (us-east-1, us-west-2)
- Standard AWS region validation
- Standard partition handling for aws
- Full service availability including Trusted Advisor
- Updated service availability checks for commercial AWS environment
"""

import os
import sys
import datetime
import json
import logging
import re
from pathlib import Path

# Global logger instance
logger = None

def setup_logging(script_name="stratusscan", log_to_file=True):
    """
    Setup comprehensive logging for StratusScan with both console and file output.

    Args:
        script_name (str): Name of the script for log file naming
        log_to_file (bool): Whether to log to file in addition to console

    Returns:
        logging.Logger: Configured logger instance
    """
    global logger

    # Create logger
    logger = logging.getLogger('stratusscan')
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    logger.handlers = []

    # Create formatters
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (if enabled)
    if log_to_file:
        try:
            # Create logs directory if it doesn't exist
            logs_dir = Path(__file__).parent / "logs"
            logs_dir.mkdir(exist_ok=True)

            # Generate timestamp for log filename: MM.DD.YYYY-HHMM
            timestamp = datetime.datetime.now().strftime("%m.%d.%Y-%H%M")
            log_filename = f"logs-{script_name}-{timestamp}.log"
            log_filepath = logs_dir / log_filename

            # File handler
            file_handler = logging.FileHandler(log_filepath, mode='w', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # Log the initialization
            logger.info(f"StratusScan logging initialized - Log file: {log_filepath}")
            logger.info(f"Script: {script_name}")
            logger.info(f"Timestamp: {timestamp}")
            logger.info("=" * 80)

        except Exception as e:
            # If file logging fails, continue with console only
            logger.error(f"Failed to setup file logging: {e}")
            logger.warning("Continuing with console logging only")

    return logger

def get_logger():
    """
    Get the current logger instance, creating one if it doesn't exist.

    Returns:
        logging.Logger: Logger instance
    """
    global logger
    if logger is None:
        logger = setup_logging()
    return logger

# Initialize with basic console logging by default
logger = get_logger()

# AWS Commercial constants
DEFAULT_REGIONS = ['us-east-1', 'us-west-2', 'us-west-1', 'eu-west-1']
AWS_PARTITION = 'aws'

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
            logger.warning("config.json not found. Using default AWS configuration.")

            # Create a default AWS config if it doesn't exist
            default_config = {
                "__comment": "StratusScan Configuration - Customize this file for your environment",
                "account_mappings": {},
                "organization_name": "YOUR-ORGANIZATION",
                "default_regions": ["us-east-1", "us-west-2", "us-west-1", "eu-west-1"],
                "aws_environment": "production",
                "resource_preferences": {
                    "ec2": {
                        "default_filter": "all",
                        "include_stopped": True,
                        "default_region": "us-east-1"
                    },
                    "vpc": {
                        "default_export_type": "all",
                        "default_region": "us-east-1"
                    },
                    "compute_optimizer": {
                        "enabled": True,
                        "note": "Available in commercial AWS"
                    }
                },
                "enabled_services": {
                    "trusted_advisor": {
                        "enabled": True,
                        "note": "Available in commercial AWS"
                    },
                    "cost_explorer": {
                        "enabled": True,
                        "note": "Available in commercial AWS"
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

def is_aws_region(region):
    """
    Check if a region is a valid AWS region.

    Args:
        region: AWS region name

    Returns:
        bool: True if valid AWS region, False otherwise
    """
    # Basic check for AWS region format
    import re
    pattern = r'^[a-z]{2}-[a-z]+-[0-9]$'
    return bool(re.match(pattern, region)) or region in DEFAULT_REGIONS

def validate_aws_region(region):
    """
    Validate that a region is a valid AWS region and provide helpful error if not.

    Args:
        region: AWS region name

    Returns:
        bool: True if valid, False otherwise
    """
    if region == "all":
        return True

    if not is_aws_region(region):
        logger.error(f"Invalid AWS region: {region}")
        logger.error(f"Valid AWS regions include: us-east-1, us-west-1, us-west-2, eu-west-1, ap-southeast-1")
        return False

    return True

def get_aws_regions():
    """
    Get list of default AWS regions.

    Returns:
        list: List of AWS region names
    """
    return DEFAULT_REGIONS.copy()

def is_aws_commercial_environment():
    """
    Check if we're currently running in an AWS Commercial environment.

    Returns:
        bool: True if in AWS Commercial, False otherwise
    """
    try:
        import boto3
        sts = boto3.client('sts')
        caller_arn = sts.get_caller_identity()["Arn"]
        return AWS_PARTITION in caller_arn
    except Exception:
        return True  # Default to commercial

def config_value(key, default=None, section=None):
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

def is_service_enabled(service_name):
    """
    Check if a service is enabled in the current AWS environment.

    Args:
        service_name: Name of the AWS service

    Returns:
        bool: True if enabled, False if disabled
    """
    if 'disabled_services' in CONFIG_DATA:
        disabled_services = CONFIG_DATA['disabled_services']
        if service_name in disabled_services:
            return disabled_services[service_name].get('enabled', False)

    return True  # Default to enabled if not explicitly disabled

def get_service_disability_reason(service_name):
    """
    Get the reason why a service is disabled.
    
    Args:
        service_name: Name of the AWS service
        
    Returns:
        str: Reason for disability or None if service is enabled
    """
    if 'disabled_services' in CONFIG_DATA:
        disabled_services = CONFIG_DATA['disabled_services']
        if service_name in disabled_services:
            return disabled_services[service_name].get('reason', 'Not available')
    
    return None

def get_default_regions():
    """
    Get the default AWS regions from configuration.

    Returns:
        list: List of default AWS region names
    """
    return CONFIG_DATA.get('default_regions', DEFAULT_REGIONS)

def get_organization_name():
    """
    Get the organization name from configuration.

    Returns:
        str: Organization name or default
    """
    return CONFIG_DATA.get('organization_name', 'YOUR-ORGANIZATION')

def get_aws_environment():
    """
    Get the AWS environment type from configuration.

    Returns:
        str: Environment type (e.g., 'production', 'staging') or default
    """
    return CONFIG_DATA.get('aws_environment', 'production')

def log_error(error_message, error_obj=None):
    """
    Log an error message to both console and file.

    Args:
        error_message: The error message to display
        error_obj: Optional exception object
    """
    current_logger = get_logger()
    if error_obj:
        current_logger.error(f"{error_message}: {str(error_obj)}")
        # Log stack trace for debugging
        current_logger.debug(f"Exception details: {error_obj}", exc_info=True)
    else:
        current_logger.error(error_message)

def log_warning(warning_message):
    """
    Log a warning message to both console and file.

    Args:
        warning_message: The warning message to display
    """
    current_logger = get_logger()
    current_logger.warning(warning_message)

def log_info(info_message):
    """
    Log an informational message to both console and file.

    Args:
        info_message: The information message to display
    """
    current_logger = get_logger()
    current_logger.info(info_message)

def log_debug(debug_message):
    """
    Log a debug message (file only, not console).

    Args:
        debug_message: The debug message to log
    """
    current_logger = get_logger()
    current_logger.debug(debug_message)

def log_success(success_message):
    """
    Log a success message to both console and file.

    Args:
        success_message: The success message to display
    """
    current_logger = get_logger()
    current_logger.info(f"SUCCESS: {success_message}")

def log_aws_info(message):
    """
    Log AWS-specific informational message to both console and file.

    Args:
        message: The AWS-specific message to display
    """
    current_logger = get_logger()
    current_logger.info(f"AWS: {message}")

def log_script_start(script_name, description=""):
    """
    Log the start of a script execution with standardized format.

    Args:
        script_name: Name of the script being executed
        description: Optional description of the script's purpose
    """
    current_logger = get_logger()
    current_logger.info("=" * 80)
    current_logger.info(f"SCRIPT START: {script_name}")
    if description:
        current_logger.info(f"DESCRIPTION: {description}")
    current_logger.info(f"START TIME: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    current_logger.info("=" * 80)

def log_script_end(script_name, start_time=None):
    """
    Log the end of a script execution with standardized format.

    Args:
        script_name: Name of the script that was executed
        start_time: Optional start time to calculate duration
    """
    current_logger = get_logger()
    end_time = datetime.datetime.now()

    current_logger.info("=" * 80)
    current_logger.info(f"SCRIPT END: {script_name}")
    current_logger.info(f"END TIME: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

    if start_time:
        duration = end_time - start_time
        current_logger.info(f"DURATION: {duration}")

    current_logger.info("=" * 80)

def log_section(section_name):
    """
    Log a section header for better log organization.

    Args:
        section_name: Name of the section
    """
    current_logger = get_logger()
    current_logger.info("-" * 50)
    current_logger.info(f"SECTION: {section_name}")
    current_logger.info("-" * 50)

def log_aws_operation(operation_name, service, region=None, details=""):
    """
    Log AWS API operations for audit trail.

    Args:
        operation_name: Name of the AWS operation (e.g., describe_instances)
        service: AWS service name (e.g., EC2)
        region: AWS region (optional)
        details: Additional details about the operation
    """
    current_logger = get_logger()
    region_info = f" in {region}" if region else ""
    details_info = f" - {details}" if details else ""
    current_logger.info(f"AWS API: {service}.{operation_name}{region_info}{details_info}")

def log_export_summary(resource_type, count, output_file):
    """
    Log export operation summary.

    Args:
        resource_type: Type of resource exported
        count: Number of resources exported
        output_file: Path to output file
    """
    current_logger = get_logger()
    current_logger.info(f"EXPORT SUMMARY: {resource_type}")
    current_logger.info(f"  Resources exported: {count}")
    current_logger.info(f"  Output file: {output_file}")

def log_system_info():
    """
    Log system information for debugging purposes.
    """
    current_logger = get_logger()
    import platform
    import sys

    current_logger.info("SYSTEM INFORMATION:")
    current_logger.info(f"  Platform: {platform.system()} {platform.release()}")
    current_logger.info(f"  Python version: {sys.version}")
    current_logger.info(f"  Working directory: {os.getcwd()}")
    current_logger.info(f"  Script location: {Path(__file__).parent}")

def log_menu_selection(menu_path, selection_name):
    """
    Log menu selections for user activity tracking.

    Args:
        menu_path: Path through menu (e.g., "4.2.1")
        selection_name: Name of the selected option
    """
    current_logger = get_logger()
    current_logger.info(f"MENU SELECTION: {menu_path} - {selection_name}")

def get_current_log_file():
    """
    Get the path to the current log file if file logging is enabled.

    Returns:
        str: Path to current log file or None if not file logging
    """
    current_logger = get_logger()
    for handler in current_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            return handler.baseFilename
    return None

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
    # AWS account IDs are 12 digits
    pattern = re.compile(r'^\d{12}$')
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
    # First validate it's an AWS region
    if not is_aws_region(region):
        return False

    try:
        import boto3

        # Try to create an EC2 client in the region
        ec2 = boto3.client('ec2', region_name=region)

        # Try a simple API call
        ec2.describe_regions(RegionNames=[region])

        return True
    except Exception as e:
        log_warning(f"Cannot access region {region}: {e}")
        return False

def get_available_aws_regions():
    """
    Get list of AWS regions that are currently accessible.

    Returns:
        list: List of accessible AWS region names
    """
    available_regions = []

    for region in DEFAULT_REGIONS:
        if check_aws_region_access(region):
            available_regions.append(region)
        else:
            log_warning(f"AWS region {region} is not accessible")

    return available_regions

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
    
    return df

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

def create_aws_arn(service, resource, region=None, account_id=None):
    """
    Create a properly formatted AWS ARN.

    Args:
        service: AWS service name
        resource: Resource identifier
        region: AWS region (optional)
        account_id: AWS account ID (optional)

    Returns:
        str: Properly formatted AWS ARN
    """
    # Use current account if not provided
    if not account_id:
        try:
            import boto3
            sts = boto3.client('sts')
            account_id = sts.get_caller_identity()["Account"]
        except Exception:
            account_id = "UNKNOWN"

    # Use default region if not provided
    if not region:
        region = get_default_regions()[0]

    return f"arn:{AWS_PARTITION}:{service}:{region}:{account_id}:{resource}"

def parse_aws_arn(arn):
    """
    Parse an AWS ARN into its components.

    Args:
        arn: AWS ARN string

    Returns:
        dict: Dictionary with ARN components or None if invalid
    """
    try:
        parts = arn.split(':')
        if len(parts) >= 6 and parts[1] == AWS_PARTITION:
            return {
                'partition': parts[1],
                'service': parts[2],
                'region': parts[3],
                'account_id': parts[4],
                'resource': ':'.join(parts[5:])
            }
    except Exception:
        pass

    return None