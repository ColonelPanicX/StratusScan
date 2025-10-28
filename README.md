# StratusScan-CLI

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![AWS](https://img.shields.io/badge/AWS-Commercial-orange.svg)](https://aws.amazon.com/)

> A comprehensive AWS resource export tool for multi-account, multi-region environments. Export detailed AWS infrastructure data to Excel with a single command.

[Quick Start](#-quick-start) • [Features](#-features) • [Installation](#-installation) • [Configuration](#%EF%B8%8F-configuration) • [Documentation](#-usage)

---

## 🚀 Quick Start

Get up and running in 5 minutes:

```bash
# 1. Clone the repository
git clone https://github.com/ColonelPanicX/StratusScan-CLI.git
cd StratusScan-CLI

# 2. Install dependencies
pip install boto3 pandas openpyxl

# 3. Configure AWS credentials (choose one)
aws configure  # Interactive setup
# OR set environment variables
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# 4. Run configuration (recommended but optional)
python configure.py

# 5. Launch StratusScan
python stratusscan.py
```

That's it! Select a resource to export from the menu and follow the prompts. Exports are saved to the `output/` directory.

---

## ✨ Features

- **🎯 Centralized Menu Interface**: Easy-to-use hierarchical menu for all export tools
- **🌍 Multi-Region Support**: Scan resources across specific regions or all AWS regions
- **🏢 Account Mapping**: Translate AWS account IDs to friendly organization names
- **📊 Standardized Exports**: Consistent Excel output with timestamp-based filenames
- **📦 Export Archive**: Built-in functionality to zip all exports into a single file
- **🔧 Dependency Management**: Automatic checking and installation of Python packages
- **💰 Cost Optimization**: Integrated billing analysis and cost optimization recommendations
- **📋 Comprehensive Reports**: All-in-one reports for Compute, Storage, and Network resources
- **💵 Pricing Integration**: Built-in EC2 and EBS pricing data for cost calculations
- **📝 Logging System**: Detailed audit trails with console and file output
- **🔐 Read-Only Operations**: Safe, non-destructive AWS resource scanning

---

## 📋 Installation

### Requirements

- **Python**: 3.6 or higher
- **AWS Access**: Configured credentials (CLI, environment variables, or IAM role)
- **Permissions**: Read-only access to AWS resources ([see details](#-aws-permissions))

### Install Dependencies

The scripts will prompt to install missing packages automatically, or you can install them manually:

```bash
pip install boto3 pandas openpyxl
```

### AWS Authentication

Configure your AWS credentials using one of these methods:

**Option 1: AWS CLI (Recommended)**
```bash
aws configure
AWS Access Key ID: [Your AWS Access Key]
AWS Secret Access Key: [Your AWS Secret Key]
Default region name: us-east-1
Default output format: json
```

**Option 2: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID="your-aws-access-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

**Option 3: IAM Instance Profile**
If running on EC2, credentials are automatically provided via the instance profile.

---

## ⚙️ Configuration

StratusScan uses a `config.json` file for account mappings and preferences.

### Interactive Setup (Recommended)

Run the configuration wizard:

```bash
python configure.py
```

This interactive tool will guide you through:
- Setting up account ID to name mappings
- Configuring default AWS regions
- Validating AWS permissions
- Checking dependencies

### Manual Configuration

Alternatively, create `config.json` manually:

```json
{
  "account_mappings": {
    "123456789012": "PROD-ACCOUNT",
    "234567890123": "DEV-ACCOUNT",
    "345678901234": "TEST-ACCOUNT"
  },
  "organization_name": "YOUR-ORGANIZATION",
  "default_regions": ["us-east-1", "us-west-2"],
  "resource_preferences": {
    "ec2": {
      "default_region": "us-east-1"
    }
  },
  "enabled_services": {
    "trusted_advisor": {
      "enabled": true,
      "note": "Available in AWS Commercial"
    }
  }
}
```

---

## 📖 Usage

### Main Menu Interface (Recommended)

```bash
python stratusscan.py
```

Navigate through the hierarchical menu to select resources:

1. Choose a category (Compute, Storage, Network, IAM, Security, Cost)
2. Select specific resource type or comprehensive report
3. Choose region(s) to scan
4. Wait for export to complete
5. Find your Excel file in `output/` directory

### Direct Script Execution

Run individual export scripts directly:

```bash
python scripts/ec2-export.py
python scripts/vpc-data-export.py
python scripts/iam-comprehensive-export.py
```

Each script will prompt for required information and save output to `output/`.

### Region Selection

When prompted, choose:
- **`all`**: Scan all AWS commercial regions
- **Specific region**: e.g., `us-east-1`, `eu-west-1`, `ap-southeast-1`

The tool validates regions and provides helpful error messages for invalid selections.

### Creating Export Archives

After running multiple exports, create a zip archive:

1. Select **Output Management** from the main menu
2. Choose **Create Output Archive**
3. Find the zip file in the root directory with format: `ACCOUNT-NAME-export-MM.DD.YYYY.zip`

---

## 🔐 AWS Permissions

StratusScan requires **read-only** access to AWS resources.

### Recommended IAM Policies

Attach these AWS managed policies to your IAM user/role:

- `ReadOnlyAccess` - General resource access
- `IAMReadOnlyAccess` - IAM resources
- `AWSSupportAccess` - Trusted Advisor (requires Business/Enterprise support)
- `ComputeOptimizerReadOnlyAccess` - Compute Optimizer recommendations
- `CostOptimizationHubReadOnlyAccess` - Cost recommendations

### Custom IAM Policy

For fine-grained control, use this custom policy:

<details>
<summary>Click to expand custom IAM policy</summary>

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:Describe*",
                "s3:GetBucketLocation",
                "s3:GetBucketVersioning",
                "s3:ListBucket",
                "s3:GetBucketAcl",
                "s3:GetBucketPolicy",
                "rds:Describe*",
                "ecs:Describe*",
                "ecs:List*",
                "eks:Describe*",
                "eks:List*",
                "elasticloadbalancing:Describe*",
                "iam:Get*",
                "iam:List*",
                "iam:GenerateCredentialReport",
                "iam:GenerateServiceLastAccessedDetails",
                "identitystore:Describe*",
                "identitystore:List*",
                "sso:Describe*",
                "sso:List*",
                "sso-admin:Describe*",
                "sso-admin:List*",
                "organizations:Describe*",
                "organizations:List*",
                "securityhub:Get*",
                "securityhub:Describe*",
                "securityhub:List*",
                "route53:Get*",
                "route53:List*",
                "route53resolver:Get*",
                "route53resolver:List*",
                "ce:GetCostAndUsage",
                "ce:GetCostForecast",
                "ce:GetUsageReport",
                "cur:DescribeReportDefinitions",
                "cost-optimization-hub:List*",
                "cost-optimization-hub:Get*",
                "compute-optimizer:GetRecommendations*",
                "compute-optimizer:Describe*",
                "support:DescribeTrustedAdvisor*",
                "support:RefreshTrustedAdvisorCheck",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```
</details>

---

## 📦 Supported AWS Resources

StratusScan supports **40+ AWS resource exporters** across multiple categories:

<details>
<summary><b>Compute Resources (5 exporters)</b></summary>

- **EC2 Instances**: Detailed instance info including OS, size, cost calculations, network config
- **ECS Clusters**: ECS cluster information, services, tasks, container instances
- **EKS Clusters**: Kubernetes cluster information, node groups, configurations
- **RDS Databases**: Database engine, size, storage, connection information
- **Compute Resources (All-in-One)**: Combined report of all compute resources

</details>

<details>
<summary><b>Storage Resources (4 exporters)</b></summary>

- **EBS Volumes**: Volume IDs, size, state, attachment info, pricing
- **EBS Snapshots**: Snapshot IDs, size, encryption status, creation dates
- **S3 Buckets**: Bucket information including size, object count, region, configuration
- **Storage Resources (All-in-One)**: Combined report of all storage resources

</details>

<details>
<summary><b>Network Resources (7 exporters)</b></summary>

- **VPC Resources**: VPCs, subnets, NAT gateways, peering connections, Elastic IPs
- **Route 53**: Hosted zones, DNS records, resolver endpoints/rules, query logging
- **Elastic Load Balancers**: Classic, Application, and Network load balancers
- **Security Groups**: Group details, inbound/outbound rules, resource associations
- **Network ACLs**: NACL rules, subnet associations, configurations
- **Route Tables**: Route table information, routes, subnet associations
- **Network Resources (All-in-One)**: Combined report of all network resources

</details>

<details>
<summary><b>IAM & Identity Resources (9 exporters)</b></summary>

- **IAM Comprehensive**: Complete IAM analysis (users, roles, policies, permissions)
- **IAM Users**: Basic user information and access keys
- **IAM Roles**: Role details, trust policies, attached permissions
- **IAM Policies**: Detailed policy analysis with risk assessment
- **IAM Identity Center Users**: AWS SSO/Identity Center users and assignments
- **IAM Identity Center Groups**: Group memberships and assignments
- **IAM Identity Center Permission Sets**: Permission set configurations
- **IAM Identity Center Comprehensive**: Complete Identity Center analysis
- **AWS Organizations**: Organizations structure, accounts, organizational units

</details>

<details>
<summary><b>Security Resources (2 exporters)</b></summary>

- **Security Hub**: Security findings, compliance status, remediation guidance
- **Services in Use**: Analysis of AWS services currently in use

</details>

<details>
<summary><b>Cost Optimization Resources (4 exporters)</b></summary>

- **Billing Export**: AWS billing and cost data
- **Cost Optimization Hub**: Recommendations and savings opportunities
- **Compute Optimizer**: Recommendations for EC2, Auto Scaling, EBS, Lambda
- **Trusted Advisor**: Cost optimization checks and recommendations (requires Business+ support)

</details>

---

## 📂 Output Files

### File Naming Convention

All exports follow a consistent naming pattern:

```
{ACCOUNT-NAME}-{RESOURCE-TYPE}-{REGION}-export-{MM.DD.YYYY}.xlsx
```

**Examples:**
- `PROD-ACCOUNT-ec2-us-east-1-export-10.27.2025.xlsx`
- `DEV-ACCOUNT-route53-all-export-10.27.2025.xlsx`
- `PROD-ACCOUNT-iam-comprehensive-export-10.27.2025.xlsx`

**Archive:**
- `ACCOUNT-NAME-export-MM.DD.YYYY.zip`

### Directory Structure

```
StratusScan-CLI/
├── stratusscan.py              # Main menu interface
├── configure.py                # Configuration wizard
├── utils.py                    # Shared utilities
├── config.json                 # Configuration file
├── README.md                   # This file
├── LICENSE                     # License information
├── reference/                  # Pricing data
│   ├── ec2-pricing.csv
│   └── ebsvol-pricing.csv
├── scripts/                    # Export scripts (40+)
│   ├── ec2-export.py
│   ├── route53-export.py
│   ├── iam-comprehensive-export.py
│   └── ... (and many more)
├── logs/                       # Execution logs
│   └── logs-{script}-{timestamp}.log
└── output/                     # Export files
    └── {exports}.xlsx
```

---

## 🐛 Troubleshooting

### Common Issues

**Missing Dependencies**
```bash
# Install required packages
pip install boto3 pandas openpyxl
```

**AWS Credentials Not Found**
```bash
# Configure AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
```

**Permission Denied Errors**
- Ensure your IAM user/role has read-only access to AWS resources
- Verify you have the necessary policies attached ([see permissions](#-aws-permissions))
- For Trusted Advisor: Requires AWS Business or Enterprise Support plan

**Invalid Region Errors**
- Use valid AWS commercial region codes (e.g., `us-east-1`, not `us-east-1a`)
- Type `all` to scan all regions
- The tool validates regions and provides helpful error messages

**Service Not Available**
- Some services have limited regional availability
- Check AWS service availability in your specific region
- Try running the export in `us-east-1` which has the broadest service availability

**Excel Export Errors**
- Ensure `openpyxl` is installed: `pip install openpyxl`
- Check disk space in the `output/` directory
- Verify write permissions to the StratusScan directory

### Getting Help

1. Check the log files in `logs/` directory for detailed error messages
2. Verify your AWS credentials: `aws sts get-caller-identity`
3. Ensure you're using valid AWS regions
4. Review the `config.json` file for any misconfigurations
5. Run `python configure.py --perms` to validate AWS permissions

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

- **Report bugs**: Open an issue with details and reproduction steps
- **Suggest features**: Share ideas for new AWS resource exporters
- **Submit PRs**: Add new exporters following the existing patterns in `scripts/`
- **Improve docs**: Help make the documentation clearer

### Adding a New Exporter

1. Create a new script in `scripts/` following the existing pattern (see `route53-export.py` as reference)
2. Import and use the `utils` module for consistency
3. Add your script to the menu in `stratusscan.py`
4. Test thoroughly across multiple regions
5. Submit a pull request

---

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with assistance from [Claude Code](https://claude.ai/code)
- Powered by [AWS SDK for Python (Boto3)](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- Excel export using [pandas](https://pandas.pydata.org/) and [openpyxl](https://openpyxl.readthedocs.io/)

---

## 📞 Support

For questions, issues, or feature requests, please open an issue on GitHub.

**Note**: This tool is designed for AWS Commercial environments. Always verify compliance with your organization's security policies and applicable regulations before use.
