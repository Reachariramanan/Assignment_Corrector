#!/usr/bin/env python3
"""
Verify Unified Installation
Checks that all necessary packages are installed correctly.

Usage:
    python verify_unified_installation.py
"""

import sys
from pathlib import Path

def check_package(package_name, import_name=None):
    """Check if a package is installed and can be imported."""
    if import_name is None:
        import_name = package_name.replace('-', '_').replace('[sse]', '')
    
    try:
        __import__(import_name)
        return True, None
    except ImportError as e:
        return False, str(e)

def main():
    print("=" * 70)
    print("YUKTA UNIFIED INSTALLATION VERIFICATION")
    print("=" * 70 + "\n")
    
    # Package mapping for imports
    packages = {
        'Core Packages': [
            ('requests', 'requests'),
            ('httpx', 'httpx'),
            ('python-dotenv', 'dotenv'),
        ],
        'LLM Provider Support': [
            ('openai', 'openai'),
            ('anthropic', 'anthropic'),
        ],
        'Model Context Protocol': [
            ('mcp', 'mcp'),
        ],
        'Data Processing & Databases': [
            ('pandas', 'pandas'),
            ('numpy', 'numpy'),
            ('sqlalchemy', 'sqlalchemy'),
            ('psycopg2-binary', 'psycopg2'),
            ('pymilvus', 'pymilvus'),
        ],
        'Async & Concurrency': [
            ('aiohttp', 'aiohttp'),
        ],
        'Observability & Tracing': [
            ('opentelemetry-api', 'opentelemetry'),
            ('opentelemetry-sdk', 'opentelemetry.sdk'),
            ('openinference-semantic-conventions', 'openinference'),
            ('arize-phoenix', 'phoenix'),
        ],
    }
    
    total = 0
    installed = 0
    missing = []
    
    for category, pkgs in packages.items():
        print(f"[{category}]")
        for pkg_name, import_name in pkgs:
            total += 1
            success, error = check_package(pkg_name, import_name)
            status = "✓" if success else "✗"
            print(f"  {status} {pkg_name:<30} ({import_name})")
            if success:
                installed += 1
            else:
                missing.append(pkg_name)
        print()
    
    # Summary
    print("=" * 70)
    print(f"Results: {installed}/{total} packages installed")
    print("=" * 70)
    
    if missing:
        print(f"\n❌ MISSING PACKAGES ({len(missing)}):")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\nTo fix, run:")
        print("   pip install -r requirements.txt")
        return 1
    else:
        print("\n✅ ALL PACKAGES INSTALLED SUCCESSFULLY!")
        print("\nYukta is ready to use. Example:")
        print("   from yukta import create_agent")
        print("   agent = create_agent('MyAgent')")
        return 0

if __name__ == "__main__":
    sys.exit(main())
