#!/usr/bin/env python3
"""
Create InfluxDB Query Templates for Site Metadata Visualization
This script creates Flux query templates that can be used in InfluxDB UI
to view site metadata in a clear table format
"""

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def create_flux_query_templates():
    """Create Flux query templates for InfluxDB UI"""
    
    templates = {
        "site_metadata_table": {
            "name": "Site Metadata - Table View",
            "description": "View site metadata in a clear table format with all fields",
            "query": '''
from(bucket: "site_1")
  |> range(start: -10y)
  |> filter(fn: (r) => r["_measurement"] == "sites_metadata")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 1)
  |> map(fn: (r) => ({
      "Site ID": r.site_id,
      "Site Name": r.site_name,
      "Location": r.location,
      "Country": r.country,
      "State": r.state,
      "Latitude": if exists r.latitude then float(v: r.latitude) else 0.0,
      "Longitude": if exists r.longitude then float(v: r.longitude) else 0.0,
      "Timezone": r.timezone,
      "Climate": r.climate,
      "Settings": if exists r.settings_json then string(v: r.settings_json) else "{}",
      "Devices Config": if exists r.devices_json then string(v: r.devices_json) else "{}",
      "Updated": r._time
    }))
'''
        },
        "all_sites_list": {
            "name": "All Sites List",
            "description": "List all available sites",
            "query": '''
import "strings"

buckets()
  |> filter(fn: (r) => r.name =~ /^site_/)
  |> map(fn: (r) => {
      site_id = strings.trimPrefix(v: r.name, prefix: "site_")
      return {site_id: site_id, bucket_name: r.name}
    })
'''
        },
        "site_metadata_formatted": {
            "name": "Site Metadata - Formatted",
            "description": "Formatted site metadata with proper types",
            "query": '''
from(bucket: "site_1")
  |> range(start: -10y)
  |> filter(fn: (r) => r["_measurement"] == "sites_metadata")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 1)
  |> map(fn: (r) => ({
      site_id: r.site_id,
      site_name: r.site_name,
      location: r.location,
      country: r.country,
      state: r.state,
      latitude: if exists r.latitude then float(v: r.latitude) else 0.0,
      longitude: if exists r.longitude then float(v: r.longitude) else 0.0,
      timezone: r.timezone,
      climate: r.climate,
      settings_json: if exists r.settings_json then string(v: r.settings_json) else "{}",
      devices_json: if exists r.devices_json then string(v: r.devices_json) else "{}",
      site_exists: if exists r["exists"] then bool(v: r["exists"]) else false,
      updated_at: r._time
    }))
'''
        }
    }
    
    return templates


def save_query_templates():
    """Save Flux query templates to file"""
    templates = create_flux_query_templates()
    
    output_dir = PROJECT_ROOT / "docs" / "influxdb_queries"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save individual query files
    for key, template in templates.items():
        query_file = output_dir / f"{key}.flux"
        with open(query_file, "w") as f:
            f.write(f"// {template['name']}\n")
            f.write(f"// {template['description']}\n\n")
            f.write(template['query'].strip())
            f.write("\n")
        print(f"✓ Saved: {query_file}")
    
    # Save combined JSON file
    json_file = output_dir / "queries.json"
    with open(json_file, "w") as f:
        json.dump(templates, f, indent=2)
    print(f"✓ Saved: {json_file}")
    
    # Create README
    readme_file = output_dir / "README.md"
    with open(readme_file, "w") as f:
        f.write("# InfluxDB Query Templates\n\n")
        f.write("These Flux queries can be used in InfluxDB UI to view site metadata.\n\n")
        f.write("## Usage\n\n")
        f.write("1. Open InfluxDB UI: http://localhost:8086\n")
        f.write("2. Go to **Data Explorer**\n")
        f.write("3. Click **Script Editor**\n")
        f.write("4. Copy and paste one of the queries below\n")
        f.write("5. **Important**: Replace `site_1` with your actual site bucket name\n")
        f.write("6. Click **Submit**\n\n")
        f.write("## Available Queries\n\n")
        
        for key, template in templates.items():
            f.write(f"### {template['name']}\n\n")
            f.write(f"{template['description']}\n\n")
            f.write("```flux\n")
            f.write(template['query'].strip())
            f.write("\n```\n\n")
            f.write(f"**File**: `{key}.flux`\n\n")
            f.write("---\n\n")
    
    print(f"✓ Saved: {readme_file}")
    print(f"\n✅ All query templates saved to: {output_dir}")


if __name__ == "__main__":
    print("Creating InfluxDB query templates...\n")
    save_query_templates()
    print("\n✅ Done! You can now use these queries in InfluxDB UI.")

