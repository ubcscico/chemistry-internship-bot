import os
import json
import requests
from jobspy import scrape_jobs
import pandas as pd

# File to track seen jobs and avoid duplicate Discord alerts
CACHE_FILE = "seen_chem_jobs.json"

def load_seen_jobs():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_jobs(seen_jobs):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(seen_jobs), f)

def send_discord_group(company, jobs_list):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL is not set.")
        return

    # Build the grouped message matching your engineering format
    message_lines = [f"🏢 **{company}**"]
    
    for job in jobs_list:
        title = job.get('title', 'N/A')
        location = job.get('location', 'N/A')
        job_url = job.get('job_url', 'N/A')
        message_lines.append(f"• **{title}** ({location})\n  🔗 {job_url}")

    payload = {"content": "\n".join(message_lines)}
    response = requests.post(webhook_url, json=payload)
    
    if response.status_code != 204:
        print(f"Failed to send Discord alert: {response.status_code}, {response.text}")

def main():
    print("=== CHEMISTRY & LIFE SCIENCES BOT INITIALIZED ===")
    
    seen_jobs = load_seen_jobs()
    new_jobs_count = 0

    # Comprehensive search terms covering chemistry, biochemistry, biotech, microbiology, and research assistant roles
    search_queries = [
        "chemistry intern", "chemistry co-op", "analytical chemist intern", 
        "biochemistry intern", "biochemistry co-op", "biotech intern", 
        "biotechnology co-op", "microbiology intern", "microbiology co-op", 
        "research assistant chemistry", "research assistant biology", 
        "laboratory assistant intern", "formulation intern", "assay development intern"
    ]

    # Target locations (Canada hubs + Pacific Northwest / California major centers)
    locations = [
        "Vancouver, BC", "Victoria, BC", "Kelowna, BC", 
        "Calgary, AB", "Edmonton, AB", "Winnipeg, MB", 
        "Markham, ON", "Montreal, QC", "Canada",
        "Seattle, WA", "Portland, OR", "San Francisco, CA", "San Diego, CA"
    ]

    all_jobs = []

    for query in search_queries:
        for location in locations:
            print(f"Searching for '{query}' in '{location}'...")
            try:
                jobs = scrape_jobs(
                    site_name=["indeed", "linkedin", "zip_recruiter", "glassdoor"],
                    search_term=query,
                    location=location,
                    results_wanted=15,
                    hours_old=72,  # Look at postings from the last 3 days
                    country_indeed='Canada' if 'Canada' in location or 'BC' in location or 'AB' in location or 'MB' in location or 'ON' in location or 'QC' in location else 'USA'
                )
                if jobs is not None and not jobs.empty:
                    all_jobs.append(jobs)
            except Exception as e:
                print(f"Error scraping query '{query}' in '{location}': {e}")

    if not all_jobs:
        print("No jobs found across current search passes.")
        return

    combined_jobs = pd.concat(all_jobs, ignore_index=True)
    # Drop exact duplicate listings based on URL
    combined_jobs = combined_jobs.drop_duplicates(subset=['job_url'])

    # Mandatory keywords: The job title MUST contain at least one of these to be included
    required_keywords = [
        "intern", "internship", "interns", 
        "co-op", "coop", "cooperative", 
        "student", "placement", "fellow", "fellowship"
    ]

    # Blacklist filters to keep out software, civil engineering, nursing, or clinical roles outside lab science
    blacklist_terms = [
        "software", "full stack", "frontend", "backend", "civil", "structural", 
        "nursing", "registered nurse", "physician", "accountant", "sales representative",
        "senior", "manager", "director", "lead"
    ]

    valid_jobs = []

    for _, row in combined_jobs.iterrows():
        job_id = str(row.get('job_url'))
        title = str(row.get('title', '')).lower()

        if job_id in seen_jobs or job_id == 'nan' or not job_id:
            continue

        # Check against blacklist
        if any(bad in title for bad in blacklist_terms):
            continue

        # Check that the title explicitly contains an internship/co-op/student keyword
        if not any(req in title for req in required_keywords):
            continue

        valid_jobs.append({
            'id': job_id,
            'title': row.get('title'),
            'company': row.get('company', 'Unknown Company'),
            'location': row.get('location', 'N/A'),
            'job_url': row.get('job_url')
        })

    # Group valid jobs by company
    company_groups = {}
    for job in valid_jobs:
        comp = job['company']
        if comp not in company_groups:
            company_groups[comp] = []
        company_groups[comp].append(job)

    # Send grouped messages per company
    for company, jobs_list in company_groups.items():
        print(f"Sending grouped alert for {company} ({len(jobs_list)} roles)...")
        send_discord_group(company, jobs_list)
        for job in jobs_list:
            seen_jobs.add(job['id'])
            new_jobs_count += 1

    save_seen_jobs(seen_jobs)
    print(f"=== SCRAPING COMPLETE. Sent {new_jobs_count} new alerts across {len(company_groups)} companies. ===")

if __name__ == "__main__":
    main()
