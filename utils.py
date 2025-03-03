#!/usr/bin/env python3
"""
===========================
= AWS RESOURCE SCANNER =
===========================

Title: StratusScan Utilities Module
Version: v1.0.0
Date: FEB-27-2025

Description:
Shared utility functions for StratusScan scripts. This module provides common
functionality such as path handling, file operations, standardized output
formatting, and account mapping that can be used across all StratusScan export scripts.
"""

import os
import sys
import datetime
import json
from pathlib import Path

# Default empty account mappings
ACCOUNT_MAPPINGS = {}

# Try to load account mappings from config file
try:
    # First try to import from a Python module
    try:
        from config import ACCOUNT_MAPPINGS as CONFIG_MAPPINGS
        ACCOUNT_MAPPINGS.update(CONFIG_MAPPINGS)
    except ImportError:
        # If Python module doesn't exist, try JSON file
        config_path = Path(__file__).parent / 'config.json'
        if config_path.exists():
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                if 'account_mappings' in config_data:
                    ACCOUNT_MAPPINGS.update(config_data['account_mappings'])
except Exception as e:
    print(f"Note: Could not load custom account mappings: {e}")
    print("Using default account mappings.")

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

def save_dataframe_to_excel(df, filename, open_after_save=False):
    """
    Save a pandas DataFrame to an Excel file in the output directory.
    
    Args:
        df: pandas DataFrame to save
        filename: Name of the file to save
        open_after_save: Whether to attempt to open the file after saving
        
    Returns:
        str: Full path to the saved file
    """
    try:
        # Import pandas here to avoid dependency issues
        import pandas as pd
        
        # Get the full path
        output_path = get_output_filepath(filename)
        
        # Save to Excel
        df.to_excel(output_path, index=False, engine='openpyxl')
        
        print(f"Data successfully exported to: {output_path}")
        
        # Try to open the file if requested
        if open_after_save:
            try:
                if sys.platform == 'win32':
                    os.startfile(output_path)
                elif sys.platform == 'darwin':  # macOS
                    import subprocess
                    subprocess.call(['open', output_path])
                else:  # Linux
                    import subprocess
                    subprocess.call(['xdg-open', output_path])
            except Exception as e:
                print(f"Could not open the file automatically: {e}")
        
        return str(output_path)
    
    except Exception as e:
        print(f"Error saving Excel file: {e}")
        
        # Try CSV as fallback
        try:
            csv_filename = filename.replace('.xlsx', '.csv')
            csv_path = get_output_filepath(csv_filename)
            
            df.to_csv(csv_path, index=False)
            print(f"Saved as CSV instead: {csv_path}")
            return str(csv_path)
            
        except Exception as csv_e:
            print(f"Error saving CSV file: {csv_e}")
            return None

def log_error(error_message, error_obj=None):
    """
    Log an error message to the console.
    
    Args:
        error_message: The error message to display
        error_obj: Optional exception object
    """
    print(f"ERROR: {error_message}")
    if error_obj:
        print(f"       {str(error_obj)}")

def log_warning(warning_message):
    """
    Log a warning message to the console.
    
    Args:
        warning_message: The warning message to display
    """
    print(f"WARNING: {warning_message}")

def log_info(info_message):
    """
    Log an informational message to the console.
    
    Args:
        info_message: The information message to display
    """
    print(f"INFO: {info_message}")

def log_success(success_message):
    """
    Log a success message to the console.
    
    Args:
        success_message: The success message to display
    """
    print(f"SUCCESS: {success_message}")
