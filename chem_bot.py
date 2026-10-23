import os
import json
import time
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

    # Build clean message matching your engineering format with suppressed link previews
    message_lines = [f"🏢 **{company}**"]
    
    for job in jobs_list:
        title = job.get('title', 'N/A')
        location = job.get('location', 'N/A')
        job_url = job.get('job_url', 'N/A')
        # Angle brackets < > around the URL suppress the large preview embed box in Discord
        message_lines.append(f"• **{title}** ({location})\n  🔗 <{job_url}>")

    payload = {"content": "\n".join(message_lines)}
    
    # Send with rate-limit handling
    while True:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 429:
            retry_after = response.json().get("retry_after", 5)
            print(f"Discord rate-limited. Retrying after {retry_after} seconds...", flush=True)
            time.sleep(retry_after)
        else:
            if response.status_code != 204:
                print(f"Failed to send Discord alert: {response.status_code}, {response.text}")
            break

def main():
    print("=== LIFE SCIENCES & HEALTH RESEARCH BOT INITIALIZED ===")
    
    seen_jobs = load_seen_jobs()
    new_jobs_count = 0

    # Focused life sciences, health sciences, and scientific research topics
    base_topics = [
        "Biochemistry", "Biologist", "Biology", "Biotechnology", "Biotech",
        "Biomedical", "Bioinformatics", "Molecular Biology", "Cell Biology",
        "Genomics", "Proteomics", "Metabolomics", "Stem Cell", "Immunology",
        "Virology", "Bacteriology", "Microbiology", "Pathology", "Histology",
        "Pharmacology", "Toxicology", "Clinical Research", "Clinical Trials",
        "Epidemiology", "Public Health", "Medical Laboratory", "Translational Research",
        "Therapeutics", "Preclinical", "Assay", "Formulation Scientist",
        "Analytical Chemistry", "Biochemist", "Bioanalytical", "RNA", "DNA",
        "Environmental Science", "Water Quality", "Conservation Science"
    ]

    # Student opportunity modifiers
    modifiers = ["intern", "internship", "co-op"]

    # Dynamically build explicit student queries
    search_queries = []
    for topic in base_topics:
        for mod in modifiers:
            search_queries.append(f"{topic} {mod}")

    # Target locations: All of Canada + Major California life science hubs
    locations = [
        "Canada",
        "San Francisco, CA", 
        "San Diego, CA", 
        "Los Angeles, CA", 
        "San Jose, CA", 
        "Irvine, CA"
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
                    results_wanted=10,  
                    hours_old=72,
                    country_indeed='Canada' if location == 'Canada' else 'USA'
                )
                if jobs is not None and not jobs.empty:
                    all_jobs.append(jobs)
            except Exception as e:
                print(f"Error scraping query '{query}' in '{location}': {e}")

    if not all_jobs:
        print("No jobs found across current search passes.")
        return

    combined_jobs = pd.concat(all_jobs, ignore_index=True)
    combined_jobs = combined_jobs.drop_duplicates(subset=['job_url'])

    # Mandatory student/internship keywords required in title
    required_student_keywords = [
        "intern", "internship", "interns", 
        "co-op", "coop", "cooperative", 
        "student", "placement", "fellow", "fellowship"
    ]

    # Mandatory science domain terms to ensure it's actually life/health/medical science
    required_science_keywords = [
        "bio", "chem", "lab", "laboratory", "research", "clinical", 
        "pharma", "genom", "molecular", "cell", "micro", "path", 
        "immun", "toxic", "data", "science", "scientific", "health", 
        "environ", "analyst", "assay", "formulation"
    ]

    # Strict blacklist to block out hardware, software, civil, mechanical, and aerospace roles
    blacklist_terms = [
        "software", "hardware", "mechanical", "electrical", "civil", "structural", 
        "wireless", "rf", "antenna", "aerospace", "drone", "robotics", "full stack", 
        "frontend", "backend", "devops", "nursing", "registered nurse", "physician", 
        "accountant", "sales", "senior", "manager", "director", "lead"
    ]

    valid_jobs = []

    for _, row in combined_jobs.iterrows():
        job_id = str(row.get('job_url'))
        title = str(row.get('title', '')).lower()

        if job_id in seen_jobs or job_id == 'nan' or not job_id:
            continue

        # Check against blacklist (instantly blocks engineering/hardware/non-science roles)
        if any(bad in title for bad in blacklist_terms):
            continue

        # Check that the title has a student modifier
        if not any(req in title for req in required_student_keywords):
            continue

        # Check that the title specifically relates to science, lab, research, or health domains
        if not any(sci in title for sci in required_science_keywords):
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
    print(f"=== SCRAPING COMPLETE. Sent {new_jobs_count} new filtered life science alerts across {len(company_groups)} companies. ===")

if __name__ == "__main__":
    main()
