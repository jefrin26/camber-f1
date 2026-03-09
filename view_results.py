#!/usr/bin/env python3
"""
Script to view and analyze the generated CSV files.
"""

import pandas as pd
import os
from pathlib import Path

# Find the most recent CSV files in outputs folder
output_dir = Path('outputs')
if not output_dir.exists():
    print("No outputs folder found. Run run_analysis.py first.")
    exit(1)

# Get all CSV files
csv_files = list(output_dir.glob('*.csv'))
if not csv_files:
    print("No CSV files found in outputs folder.")
    exit(1)

print("=" * 60)
print("CAMBER F1 - ANALYSIS RESULTS VIEWER")
print("=" * 60)

# Show available files
print("\n📁 Available CSV files:")
for i, file in enumerate(csv_files, 1):
    size_kb = file.stat().st_size / 1024
    print(f"  {i}. {file.name} ({size_kb:.1f} KB)")

print("\n" + "=" * 60)

# Let user choose which file to view
choice = input("\nEnter file number to view (or 'all' to view both): ")

if choice.lower() == 'all':
    # View both files
    for file in csv_files:
        print(f"\n📊 Analyzing: {file.name}")
        print("-" * 40)
        
        df = pd.read_csv(file)
        print(f"Rows: {len(df)}")
        print(f"Columns: {list(df.columns)}")
        print("\nFirst 5 rows:")
        print(df.head())
        print("\nBasic statistics:")
        print(df.describe())
        
        if 'Stint' in df.columns and len(df) > 0:
            print(f"\nUnique stints: {df['Stint'].unique()}")
        
        if 'Compound' in df.columns:
            print(f"\nCompound distribution:")
            print(df['Compound'].value_counts())
        
        print("\n" + "=" * 40)
        
else:
    try:
        file_idx = int(choice) - 1
        selected_file = csv_files[file_idx]
        
        print(f"\n📊 Analyzing: {selected_file.name}")
        print("-" * 40)
        
        df = pd.read_csv(selected_file)
        
        # Basic info
        print(f"\n📈 Data Overview:")
        print(f"  - Total rows: {len(df)}")
        print(f"  - Total columns: {len(df.columns)}")
        print(f"  - Memory usage: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")
        
        # Column info
        print(f"\n📋 Columns:")
        for col in df.columns:
            dtype = df[col].dtype
            nulls = df[col].isnull().sum()
            print(f"  - {col}: {dtype} (nulls: {nulls})")
        
        # Preview data
        print(f"\n🔍 First 10 rows:")
        print(df.head(10).to_string())
        
        # Basic statistics
        print(f"\n📊 Statistics for numeric columns:")
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        if len(numeric_cols) > 0:
            print(df[numeric_cols].describe().to_string())
        
        # Specific analysis based on file type
        if 'laps' in selected_file.name:
            print(f"\n🏁 Lap Analysis:")
            if 'Compound' in df.columns:
                print(f"\nCompounds used: {df['Compound'].unique()}")
            
            if 'HealthScore' in df.columns:
                print(f"\nTire Health:")
                print(f"  - Average: {df['HealthScore'].mean():.1f}%")
                print(f"  - Minimum: {df['HealthScore'].min():.1f}%")
                print(f"  - Maximum: {df['HealthScore'].max():.1f}%")
            
            if 'DegradationDelta' in df.columns:
                print(f"\nDegradation (seconds slower than fresh tire):")
                print(f"  - Average: {df['DegradationDelta'].mean():.3f}s")
                print(f"  - Maximum: {df['DegradationDelta'].max():.3f}s")
        
        elif 'stints' in selected_file.name:
            print(f"\n🔄 Stint Analysis:")
            print(df.to_string())
            
    except (ValueError, IndexError):
        print("Invalid selection!")

print("\n✅ Done!")